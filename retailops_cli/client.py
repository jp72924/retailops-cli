"""
retailops_cli.client
--------------------
Synchronous HTTP client wrapping the RetailOps REST API.

Design notes:
- Uses httpx.Client (synchronous) — no event-loop overhead in a CLI context.
- Mirrors the path/param-cleaning conventions in the MCP server's async client.
- Retries up to 3 times on 429 Too Many Requests, respecting Retry-After.
- Verbose mode prints request/response lines to stderr via Rich (does not
  corrupt --output json / csv pipelines which go to stdout).
- Raises RetailOpsError for all non-2xx responses.
- Raises httpx.ConnectError / httpx.TimeoutException on network failures
  (callers should catch and forward to handle_connection_error).
"""

from __future__ import annotations

import time
from typing import Any

import httpx

from .config import Profile
from .errors import RetailOpsError, raise_for_status


class RetailOpsClient:
    """
    Thin synchronous wrapper around the RetailOps REST API (/api/v1/).

    Methods
    -------
    get(path, params)       → dict | list
    post(path, body)        → dict | None
    post_anon(path, body)   → dict          (no Authorization header)
    patch(path, body)       → dict
    put(path, body)         → dict
    delete(path)            → None
    """

    _MAX_RETRIES = 3

    def __init__(
        self,
        profile: Profile,
        verbose: bool = False,
        auth_scheme: str = "Token",
    ) -> None:
        self._verbose = verbose
        self._base    = profile.base_url.rstrip("/") + "/"

        _common = {
            "Accept": "application/json",
        }

        headers = dict(_common)
        if profile.token:
            headers["Authorization"] = f"{auth_scheme} {profile.token}"

        self._http = httpx.Client(
            base_url=self._base,
            headers=headers,
            timeout=profile.timeout,
            verify=profile.verify_ssl,
        )
        # Unauthenticated client — used only for POST /auth/token/ (login).
        self._anon = httpx.Client(
            base_url=self._base,
            headers=_common,
            timeout=profile.timeout,
            verify=profile.verify_ssl,
        )

    # ── internal helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _norm(path: str) -> str:
        """Strip leading slash so the path resolves relative to base_url."""
        return path.lstrip("/")

    @staticmethod
    def _clean_params(params: dict | None) -> dict:
        """Remove None-valued query params (avoids sending literal 'None')."""
        return {k: v for k, v in (params or {}).items() if v is not None}

    @staticmethod
    def _clean_body(body: dict | None) -> dict:
        """Remove None-valued body fields (true partial-update semantics)."""
        return {k: v for k, v in (body or {}).items() if v is not None}

    @staticmethod
    def _clean_form_data(body: dict | None) -> dict:
        """Remove None fields and stringify form values for multipart requests."""
        cleaned = {}
        for key, value in (body or {}).items():
            if value is None:
                continue
            if isinstance(value, bool):
                cleaned[key] = "true" if value else "false"
            else:
                cleaned[key] = str(value)
        return cleaned

    def _log(self, method: str, path: str) -> None:
        if self._verbose:
            from rich.console import Console
            Console(stderr=True).print(f"[dim]→ {method} {self._base}{path}[/dim]")

    def _log_response(self, r: httpx.Response) -> None:
        if self._verbose:
            from rich.console import Console
            color = "green" if r.is_success else "red"
            Console(stderr=True).print(f"[dim][{color}]← {r.status_code}[/{color}][/dim]")

    def _send(self, fn, path: str, **kwargs) -> httpx.Response:
        """
        Execute an HTTP call with automatic retry on 429 (rate limit).
        Returns the final httpx.Response; raises RetailOpsError on non-2xx.
        """
        last: httpx.Response | None = None
        for attempt in range(self._MAX_RETRIES):
            r = fn(path, **kwargs)
            self._log_response(r)
            last = r
            if r.status_code != 429 or attempt == self._MAX_RETRIES - 1:
                break
            delay = int(r.headers.get("Retry-After", "5"))
            if self._verbose:
                from rich.console import Console
                Console(stderr=True).print(
                    f"[yellow]Rate limited. Retrying in {delay}s "
                    f"(attempt {attempt + 1}/{self._MAX_RETRIES})…[/yellow]"
                )
            time.sleep(delay)

        raise_for_status(last)
        return last

    # ── public API ────────────────────────────────────────────────────────────

    def get(self, path: str, params: dict | None = None) -> Any:
        p = self._norm(path)
        self._log("GET", p)
        r = self._send(self._http.get, p, params=self._clean_params(params))
        return r.json() if r.content else None

    def post(self, path: str, body: dict | None = None) -> Any:
        p = self._norm(path)
        self._log("POST", p)
        r = self._send(self._http.post, p, json=self._clean_body(body))
        return r.json() if r.content and r.status_code != 204 else None

    def post_multipart(
        self,
        path: str,
        data: dict | None = None,
        files: dict | None = None,
    ) -> Any:
        p = self._norm(path)
        self._log("POST(multipart)", p)
        r = self._send(
            self._http.post,
            p,
            data=self._clean_form_data(data),
            files=files or {},
        )
        return r.json() if r.content and r.status_code != 204 else None

    def post_anon(self, path: str, body: dict) -> dict:
        """POST without an Authorization header (used for login)."""
        p = self._norm(path)
        self._log("POST(anon)", p)
        r = self._send(self._anon.post, p, json=body)
        return r.json()

    def patch(self, path: str, body: dict) -> Any:
        p = self._norm(path)
        self._log("PATCH", p)
        r = self._send(self._http.patch, p, json=self._clean_body(body))
        return r.json() if r.content else None

    def patch_multipart(
        self,
        path: str,
        data: dict | None = None,
        files: dict | None = None,
    ) -> Any:
        p = self._norm(path)
        self._log("PATCH(multipart)", p)
        r = self._send(
            self._http.patch,
            p,
            data=self._clean_form_data(data),
            files=files or {},
        )
        return r.json() if r.content else None

    def put(self, path: str, body: dict) -> Any:
        p = self._norm(path)
        self._log("PUT", p)
        r = self._send(self._http.put, p, json=self._clean_body(body))
        return r.json() if r.content else None

    def delete(self, path: str) -> None:
        p = self._norm(path)
        self._log("DELETE", p)
        self._send(self._http.delete, p)

    def get_text(
        self,
        path: str,
        params: dict | None = None,
        accept: str | None = None,
    ) -> str:
        p = self._norm(path)
        self._log("GET", p)
        headers = {"Accept": accept} if accept else None
        r = self._send(
            self._http.get,
            p,
            params=self._clean_params(params),
            headers=headers,
        )
        return r.text

    def close(self) -> None:
        """Release underlying connection pools."""
        self._http.close()
        self._anon.close()

    # ── context manager support ───────────────────────────────────────────────

    def __enter__(self) -> "RetailOpsClient":
        return self

    def __exit__(self, *_) -> None:
        self.close()
