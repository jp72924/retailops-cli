"""
commands/schema.py
------------------
OpenAPI schema helpers.
"""

from __future__ import annotations

import sys
from typing import Optional

import httpx
import typer

from .. import state
from ..config import get_profile
from ..errors import RetailOpsError, handle_connection_error, handle_error
from ..output import console

app = typer.Typer(no_args_is_help=True)


def _client():
    from ..client import RetailOpsClient
    return RetailOpsClient(get_profile(state.profile), verbose=state.verbose)


def _url(path: str) -> str:
    return get_profile(state.profile).base_url.rstrip("/") + "/" + path.lstrip("/")


@app.command(name="get")
def get_schema(
    format_: str = typer.Option("yaml", "--format", "-f", help="yaml | json"),
) -> None:
    """Download the raw OpenAPI schema."""
    fmt = format_.strip().lower()
    if fmt not in {"yaml", "json"}:
        from ..errors import err_console
        err_console.print("[red]Invalid --format.[/red] Choose yaml or json.")
        raise typer.Exit(1)

    params = {"format": "json"} if fmt == "json" else None
    accept = "application/json" if fmt == "json" else "application/vnd.oai.openapi"
    try:
        with _client() as client:
            text = client.get_text("schema/", params=params, accept=accept)
    except RetailOpsError as e:
        handle_error(e)
        return
    except httpx.ConnectError as e:
        handle_connection_error(e, get_profile(state.profile).base_url)
        return

    sys.stdout.write(text)
    if not text.endswith("\n"):
        sys.stdout.write("\n")


@app.command(name="swagger-url")
def swagger_url() -> None:
    """Print the Swagger UI URL for the active profile."""
    console.print(_url("schema/swagger/"))


@app.command(name="redoc-url")
def redoc_url() -> None:
    """Print the ReDoc URL for the active profile."""
    console.print(_url("schema/redoc/"))
