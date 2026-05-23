"""
commands/roles.py
-----------------
  retailops-cli roles list   — list all system roles
  retailops-cli roles get    <id>

Roles are seeded read-only reference data (Admin=1, Manager=2, Staff=3).
Permissions: Admin only.
"""

from __future__ import annotations

from typing import Optional

import httpx
import typer

from .. import state
from ..config import get_profile
from ..errors import RetailOpsError, handle_error, handle_connection_error
from ..output import render

app = typer.Typer(no_args_is_help=True)


def _client():
    from ..client import RetailOpsClient
    return RetailOpsClient(get_profile(state.profile), verbose=state.verbose)


# ── list ──────────────────────────────────────────────────────────────────────

@app.command(name="list")
def list_roles(
    output: Optional[str] = typer.Option(None, "--output", "-o"),
) -> None:
    """List all system roles (Admin only)."""
    fmt = output or state.output
    try:
        with _client() as client:
            data = client.get("roles/")
    except RetailOpsError as e:
        handle_error(e)
        return
    except httpx.ConnectError as e:
        handle_connection_error(e, get_profile(state.profile).base_url)
        return
    render(data, fmt, columns=["id", "name"])


# ── get ───────────────────────────────────────────────────────────────────────

@app.command()
def get(
    id:     int           = typer.Argument(..., help="Role ID."),
    output: Optional[str] = typer.Option(None, "--output", "-o"),
) -> None:
    """Retrieve a single role by ID (Admin only)."""
    fmt = output or state.output
    try:
        with _client() as client:
            data = client.get(f"roles/{id}/")
    except RetailOpsError as e:
        handle_error(e)
        return
    except httpx.ConnectError as e:
        handle_connection_error(e, get_profile(state.profile).base_url)
        return
    render(data, fmt)
