"""
retailops_cli.errors
--------------------
Error types, HTTP error parsing, and CLI exit-code mapping.

This module is self-contained — it does not import from the RetailOps
Django project or its MCP server layer.

Exit codes:
  0  Success
  1  API error (generic 4xx / 5xx), or a bulk operation in which any item failed
  2  Configuration error (missing token, bad profile, connection refused, timeout)
  3  Not found (404)
  4  Permission denied (403)
  130 Aborted by user (Ctrl-C or declined confirmation prompt)

Note on bulk operations: the API answers HTTP 200 even when every item in the
batch failed, so partial and total failure are both reported as exit 1. A
script that needs the distinction should read the succeeded/failed arrays from
--output json rather than branching on the exit code.
"""

from __future__ import annotations

import httpx
import typer
from rich.console import Console

from . import state

err_console = Console(stderr=True)


# ── exception class ───────────────────────────────────────────────────────────

class RetailOpsError(Exception):
    """
    Raised for any non-2xx response from the RetailOps API.

    Attributes:
        status  : HTTP status code.
        error   : Human-readable message from the API envelope.
        code    : Machine-readable code from the API envelope.
        details : Field-level validation errors (only present on 400).
    """

    def __init__(
        self,
        status: int,
        error: str,
        code: str,
        details: dict | None = None,
    ) -> None:
        self.status  = status
        self.error   = error
        self.code    = code
        self.details = details or {}
        super().__init__(f"[{status}] {code}: {error}")

    # ── human messages ────────────────────────────────────────────────────────

    def _format_details(self) -> str:
        """
        Flatten field-level errors into "field: msg; field: msg".

        Handles both the DRF shape ({"field": ["msg", ...]}) and the scalar
        shape the OCR pipeline returns ({"missing_fields": "..."}).
        """
        lines = []
        for field, msgs in self.details.items():
            text = ", ".join(str(m) for m in msgs) if isinstance(msgs, list) else str(msgs)
            lines.append(f"{field}: {text}")
        return "; ".join(lines)

    def user_message(self) -> str:
        # Order matters: this is a first-match-wins chain.
        if self.status == 401 or self.code in ("authentication_failed", "not_authenticated"):
            return (
                "Authentication failed. Run [bold]retailops-cli auth login[/bold] to obtain a token, "
                "or check that the token in your config profile is still valid."
            )
        if self.status == 403 or self.code == "permission_denied":
            return "Permission denied. Your account role is insufficient for this action."
        if self.status == 404 or self.code == "not_found":
            return f"Not found. {self.error}"
        if self.status == 409 or self.code in ("conflict", "wrong_status"):
            return f"Conflict: {self.error}"
        if self.status == 429 or self.code == "throttled":
            return f"Rate limited: {self.error}"
        if self.code == "account_disabled":
            return "This account has been deactivated. Contact an Admin to reactivate it."
        # 413 / 415 / 422 come from the receipt-verification pipeline. Without
        # these branches they fall through to the generic tail, which drops
        # `details` — exactly where the useful part of the message lives.
        if self.status == 413:
            return f"File too large: {self.error}"
        if self.status == 415:
            return f"Unsupported file type: {self.error}"
        if self.status == 422:
            if self.details:
                return f"Could not process: {self.error} — {self._format_details()}"
            return f"Could not process: {self.error}"
        if self.status == 400:
            if self.details:
                return "Validation failed — " + self._format_details()
            return f"Validation failed — {self.error}"
        if self.status >= 500:
            # A 5xx carrying a real error code — an upstream rate source
            # failing with 502, say — has a message worth showing. A genuine
            # unhandled 500 does not: self.error is then an HTML traceback
            # page or a placeholder, so fall back to the log hint.
            if self.code not in ("http_error", "unknown", "server_error"):
                return f"Server error (HTTP {self.status}): {self.error}"
            return f"Server error (HTTP {self.status}). Check the RetailOps server logs."
        return f"{self.error} (HTTP {self.status}, code={self.code})"

    def exit_code(self) -> int:
        if self.status == 404:
            return 3
        if self.status == 403:
            return 4
        if self.status in (401, 0):
            return 2
        return 1


# ── HTTP response parser ──────────────────────────────────────────────────────

def raise_for_status(response: httpx.Response) -> None:
    """Raise RetailOpsError for any non-2xx httpx Response."""
    if response.is_success:
        return
    try:
        body = response.json()
        if not isinstance(body, dict):
            # A valid-JSON non-object body (a bare list or string, as proxies
            # sometimes return on 415/502) would otherwise raise AttributeError
            # on .get() and escape as a traceback.
            #
            # ValueError specifically, not TypeError: the except clause below
            # catches it and falls back to the raw-text envelope. A TypeError
            # would escape — which is the bug this guard exists to prevent.
            raise ValueError("error envelope is not a JSON object")
        raise RetailOpsError(
            status=response.status_code,
            error=body.get("error", "Unknown error"),
            code=body.get("code", "unknown"),
            details=body.get("details"),
        )
    except (ValueError, KeyError):
        raise RetailOpsError(
            status=response.status_code,
            error=response.text or f"HTTP {response.status_code}",
            code="http_error",
        )


# ── CLI error handlers ────────────────────────────────────────────────────────

def handle_error(e: RetailOpsError) -> None:
    """Print a styled error message and exit with the appropriate exit code."""
    err_console.print(f"[red]Error:[/red] {e.user_message()}")
    raise typer.Exit(e.exit_code())


def handle_connection_error(e: Exception, base_url: str) -> None:
    """
    Handle httpx transport failures (connection refused, timeout, DNS) with a
    friendly message instead of a traceback.

    A timeout means the server answered the connection but not in time, so
    "is it running?" is the wrong hint — point at the timeout instead.
    """
    if isinstance(e, httpx.TimeoutException):
        err_console.print(f"[red]Timed out:[/red] No response from [bold]{base_url}[/bold] in time")
        err_console.print(
            "[dim]The server may be slow or overloaded. Raise 'timeout' in your config "
            "profile if this keeps happening.[/dim]"
        )
    else:
        err_console.print(f"[red]Connection error:[/red] Cannot reach [bold]{base_url}[/bold]")
        err_console.print("[dim]Is the RetailOps server running?[/dim]")
    if str(e):
        err_console.print(f"[dim]{e}[/dim]")
    raise typer.Exit(2)


def abort(message: str = "Aborted.") -> None:
    """Print an abort message and exit 130 (standard Ctrl-C exit code)."""
    err_console.print(f"[yellow]{message}[/yellow]")
    raise typer.Exit(130)


def confirm_or_abort(message: str, *, default: bool = False) -> None:
    """
    Prompt before a destructive action, unless the user has opted out.

    Skipped for --yes (an explicit opt-out) and for --dry-run: nothing is sent
    under a dry run, so there is nothing to confirm — client._send() prints the
    preview and exits 0 on its own. Exits 130 when the user declines.

    Centralising this is what keeps --dry-run and confirmation in step. The two
    used to be wired command by command, which is how eight commands ended up
    honouring --dry-run and thirty-seven ignoring it.
    """
    if state.yes or state.dry_run:
        return
    if not typer.confirm(message, default=default):
        abort()
