"""
retailops_cli.errors
--------------------
Error types, HTTP error parsing, and CLI exit-code mapping.

This module is self-contained — it does not import from the RetailOps
Django project or its MCP server layer.

Exit codes:
  0  Success
  1  API error (generic 4xx / 5xx)
  2  Configuration error (missing token, bad profile, connection refused)
  3  Not found (404)
  4  Permission denied (403)
  130 Aborted by user (Ctrl-C or declined confirmation prompt)
"""

from __future__ import annotations

import httpx
import typer
from rich.console import Console

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

    def user_message(self) -> str:
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
        if self.status == 400:
            if self.details:
                lines = []
                for field, msgs in self.details.items():
                    text = ", ".join(msgs) if isinstance(msgs, list) else str(msgs)
                    lines.append(f"{field}: {text}")
                return "Validation failed — " + "; ".join(lines)
            return f"Validation failed — {self.error}"
        if self.status >= 500:
            return "Server error (HTTP 500). Check the RetailOps server logs."
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
    """Handle httpx connection / timeout failures with a friendly message."""
    err_console.print(f"[red]Connection error:[/red] Cannot reach [bold]{base_url}[/bold]")
    err_console.print("[dim]Is the RetailOps server running?[/dim]")
    if str(e):
        err_console.print(f"[dim]{e}[/dim]")
    raise typer.Exit(2)


def abort(message: str = "Aborted.") -> None:
    """Print an abort message and exit 130 (standard Ctrl-C exit code)."""
    err_console.print(f"[yellow]{message}[/yellow]")
    raise typer.Exit(130)
