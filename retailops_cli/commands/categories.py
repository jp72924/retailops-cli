"""
commands/categories.py
----------------------
  retailops-cli categories list   [--search TEXT] [--ordering FIELD] [--page N] [--all]
  retailops-cli categories get    <id>
  retailops-cli categories create --name NAME [--description TEXT] [--parent-id INT]
  retailops-cli categories update <id> [--name NAME] [--description TEXT] [--parent-id INT]
  retailops-cli categories delete <id>

Permissions: read = any authenticated; write = Manager+.
"""

from __future__ import annotations

from typing import Optional

import httpx
import typer

from .. import state
from ..config import get_profile
from ..errors import RetailOpsError, abort, handle_error, handle_connection_error
from ..output import console, print_success, render
from ..pager import fetch_all, paginated_get

app = typer.Typer(no_args_is_help=True)


def _client():
    from ..client import RetailOpsClient
    return RetailOpsClient(get_profile(state.profile), verbose=state.verbose)


# ── list ──────────────────────────────────────────────────────────────────────

@app.command(name="list")
def list_categories(
    search:   Optional[str] = typer.Option(None, "--search",   "-s", help="Search name/description."),
    ordering: Optional[str] = typer.Option(None, "--ordering", "-O", help="Sort field, e.g. name or -created_at."),
    page:     int            = typer.Option(1,    "--page",     "-p", help="Page number."),
    all_:     bool           = typer.Option(False,"--all",            help="Fetch all pages.", is_flag=True),
    output:   Optional[str]  = typer.Option(None, "--output",  "-o"),
) -> None:
    """List product categories."""
    fmt    = output or state.output
    params = {"search": search, "ordering": ordering}
    try:
        with _client() as client:
            data = fetch_all(client, "categories/", params) if all_ \
                   else paginated_get(client, "categories/", params, page, state.page_size)
    except RetailOpsError as e:
        handle_error(e)
        return
    except httpx.ConnectError as e:
        handle_connection_error(e, get_profile(state.profile).base_url)
        return
    render(data, fmt, columns=["id", "name", "display_name", "parent_category", "created_at"])


# ── get ───────────────────────────────────────────────────────────────────────

@app.command()
def get(
    id:     int            = typer.Argument(..., help="Category ID."),
    output: Optional[str]  = typer.Option(None, "--output", "-o"),
) -> None:
    """Retrieve a single category."""
    fmt = output or state.output
    try:
        with _client() as client:
            data = client.get(f"categories/{id}/")
    except RetailOpsError as e:
        handle_error(e)
        return
    except httpx.ConnectError as e:
        handle_connection_error(e, get_profile(state.profile).base_url)
        return
    render(data, fmt)


# ── create ────────────────────────────────────────────────────────────────────

@app.command()
def create(
    name:        str           = typer.Option(..., "--name",        "-n", prompt=True, help="Category name (unique)."),
    description: Optional[str] = typer.Option(None,"--description", "-d", help="Optional description."),
    parent_id:   Optional[int] = typer.Option(None,"--parent-id",         help="Parent category ID (creates a subcategory)."),
    output:      Optional[str] = typer.Option(None, "--output",    "-o"),
) -> None:
    """Create a new category. Requires Manager role."""
    fmt = output or state.output
    try:
        with _client() as client:
            data = client.post("categories/", {
                "name":            name,
                "description":     description,
                "parent_category": parent_id,
            })
    except RetailOpsError as e:
        handle_error(e)
        return
    except httpx.ConnectError as e:
        handle_connection_error(e, get_profile(state.profile).base_url)
        return
    print_success(f"Category '{data['name']}' created (id={data['id']}).")
    render(data, fmt)


# ── update ────────────────────────────────────────────────────────────────────

@app.command()
def update(
    id:          int            = typer.Argument(..., help="Category ID."),
    name:        Optional[str]  = typer.Option(None, "--name",        "-n"),
    description: Optional[str]  = typer.Option(None, "--description", "-d"),
    parent_id:   Optional[int]  = typer.Option(None, "--parent-id"),
    output:      Optional[str]  = typer.Option(None, "--output",     "-o"),
) -> None:
    """Update category fields. Requires Manager role. Only supplied fields are changed."""
    if not any([name, description, parent_id is not None]):
        console.print("[yellow]No fields supplied. Nothing to update.[/yellow]")
        raise typer.Exit(0)
    fmt = output or state.output
    body: dict = {}
    if name        is not None: body["name"]            = name
    if description is not None: body["description"]     = description
    if parent_id   is not None: body["parent_category"] = parent_id
    try:
        with _client() as client:
            data = client.patch(f"categories/{id}/", body)
    except RetailOpsError as e:
        handle_error(e)
        return
    except httpx.ConnectError as e:
        handle_connection_error(e, get_profile(state.profile).base_url)
        return
    print_success(f"Category {id} updated.")
    render(data, fmt)


# ── delete ────────────────────────────────────────────────────────────────────

@app.command()
def delete(
    id: int = typer.Argument(..., help="Category ID."),
) -> None:
    """Delete a category. Requires Manager role. Blocked if the category has products."""
    if not state.yes:
        confirmed = typer.confirm(f"Delete category {id}?", default=False)
        if not confirmed:
            abort()
    try:
        with _client() as client:
            client.delete(f"categories/{id}/")
    except RetailOpsError as e:
        handle_error(e)
        return
    except httpx.ConnectError as e:
        handle_connection_error(e, get_profile(state.profile).base_url)
        return
    print_success(f"Category {id} deleted.")
