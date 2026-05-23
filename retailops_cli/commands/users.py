"""
commands/users.py
-----------------
  retailops-cli users list       [--search TEXT] [--ordering FIELD] [--page N] [--all]
  retailops-cli users get        <id>
  retailops-cli users create     --email EMAIL --first-name NAME --last-name NAME --role INT --password PW
  retailops-cli users update     <id> [field flags]
  retailops-cli users passwd     <id>
  retailops-cli users deactivate <id>
  retailops-cli users reactivate <id>

Permissions: Admin only (except `get` for own profile).
"""

from __future__ import annotations

from typing import Optional

import httpx
import typer

from .. import state
from ..config import get_profile
from ..errors import RetailOpsError, abort, handle_error, handle_connection_error
from ..output import console, print_dry_run, print_success, render
from ..pager import fetch_all, paginated_get

app = typer.Typer(no_args_is_help=True)


def _client():
    from ..client import RetailOpsClient
    return RetailOpsClient(get_profile(state.profile), verbose=state.verbose)


# ── list ──────────────────────────────────────────────────────────────────────

@app.command(name="list")
def list_users(
    search:   Optional[str] = typer.Option(None,  "--search",   "-s"),
    ordering: Optional[str] = typer.Option(None,  "--ordering", "-O", help="e.g. email or -created_at"),
    page:     int            = typer.Option(1,     "--page",     "-p"),
    all_:     bool           = typer.Option(False, "--all",            is_flag=True),
    output:   Optional[str]  = typer.Option(None,  "--output",  "-o"),
) -> None:
    """List system users (Admin only)."""
    fmt    = output or state.output
    params = {"search": search, "ordering": ordering}
    try:
        with _client() as client:
            data = fetch_all(client, "users/", params) if all_ \
                   else paginated_get(client, "users/", params, page, state.page_size)
    except RetailOpsError as e:
        handle_error(e)
        return
    except httpx.ConnectError as e:
        handle_connection_error(e, get_profile(state.profile).base_url)
        return
    render(data, fmt, columns=["id", "email", "first_name", "last_name", "role_name", "is_active", "created_at"])


# ── get ───────────────────────────────────────────────────────────────────────

@app.command()
def get(
    id:     int           = typer.Argument(..., help="User ID."),
    output: Optional[str] = typer.Option(None, "--output", "-o"),
) -> None:
    """Retrieve a user. Admins can view any user; others may only view themselves."""
    fmt = output or state.output
    try:
        with _client() as client:
            data = client.get(f"users/{id}/")
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
    email:      str           = typer.Option(...,  "--email",      "-e", prompt=True),
    first_name: str           = typer.Option(...,  "--first-name", "-f", prompt=True),
    last_name:  str           = typer.Option(...,  "--last-name",  "-l", prompt=True),
    role:       int           = typer.Option(...,  "--role",       "-r", prompt=True,
                                              help="Role primary key. Run 'retailops-cli roles list' to see available roles."),
    password:   str           = typer.Option(...,  "--password",   "-P",
                                              prompt=True, hide_input=True,
                                              confirmation_prompt=True),
    is_active:  bool          = typer.Option(True, "--active/--inactive"),
    timezone:   Optional[str] = typer.Option(None, "--timezone",
                                              help="IANA timezone, e.g. America/New_York. Defaults to UTC."),
    language:   Optional[str] = typer.Option(None, "--language",
                                              help="Language code, e.g. en, es. Defaults to en."),
    output:     Optional[str] = typer.Option(None, "--output", "-o"),
) -> None:
    """Create a new user (Admin only)."""
    fmt = output or state.output
    try:
        with _client() as client:
            data = client.post("users/", {
                "email":      email,
                "first_name": first_name,
                "last_name":  last_name,
                "role":       role,
                "password":   password,
                "is_active":  is_active,
                "timezone":   timezone,
                "language":   language,
            })
    except RetailOpsError as e:
        handle_error(e)
        return
    except httpx.ConnectError as e:
        handle_connection_error(e, get_profile(state.profile).base_url)
        return
    print_success(f"User '{data['email']}' created (id={data['id']}).")
    render(data, fmt)


# ── update ────────────────────────────────────────────────────────────────────

@app.command()
def update(
    id:         int            = typer.Argument(..., help="User ID."),
    email:      Optional[str]  = typer.Option(None, "--email",      "-e"),
    first_name: Optional[str]  = typer.Option(None, "--first-name", "-f"),
    last_name:  Optional[str]  = typer.Option(None, "--last-name",  "-l"),
    role:       Optional[int]  = typer.Option(None, "--role",       "-r", help="Role primary key. Run 'retailops-cli roles list' to see available roles."),
    timezone:   Optional[str]  = typer.Option(None, "--timezone",         help="IANA timezone, e.g. Europe/London."),
    language:   Optional[str]  = typer.Option(None, "--language",         help="Language code, e.g. en, es."),
    output:     Optional[str]  = typer.Option(None, "--output",    "-o"),
) -> None:
    """Update user profile fields (Admin only). Only supplied fields are changed."""
    body: dict = {}
    if email      is not None: body["email"]      = email
    if first_name is not None: body["first_name"] = first_name
    if last_name  is not None: body["last_name"]  = last_name
    if role       is not None: body["role"]       = role
    if timezone   is not None: body["timezone"]   = timezone
    if language   is not None: body["language"]   = language
    if not body:
        console.print("[yellow]No fields supplied. Nothing to update.[/yellow]")
        raise typer.Exit(0)
    fmt = output or state.output
    try:
        with _client() as client:
            data = client.patch(f"users/{id}/", body)
    except RetailOpsError as e:
        handle_error(e)
        return
    except httpx.ConnectError as e:
        handle_connection_error(e, get_profile(state.profile).base_url)
        return
    print_success(f"User {id} updated.")
    render(data, fmt)


# ── change password ───────────────────────────────────────────────────────────

@app.command()
def passwd(
    id: int = typer.Argument(..., help="User ID."),
) -> None:
    """Set a new password for a user (Admin only)."""
    new_password = typer.prompt("New password", hide_input=True)
    confirm      = typer.prompt("Confirm password", hide_input=True)
    if new_password != confirm:
        from ..errors import err_console
        err_console.print("[red]Passwords do not match.[/red]")
        raise typer.Exit(1)
    try:
        with _client() as client:
            data = client.post(f"users/{id}/change-password/", {
                "new_password":     new_password,
                "confirm_password": confirm,
            })
    except RetailOpsError as e:
        handle_error(e)
        return
    except httpx.ConnectError as e:
        handle_connection_error(e, get_profile(state.profile).base_url)
        return
    print_success(data.get("detail", f"Password updated for user {id}."))


# ── deactivate / reactivate ───────────────────────────────────────────────────

@app.command()
def deactivate(
    id: int = typer.Argument(..., help="User ID."),
) -> None:
    """Deactivate a user account (Admin only). Cannot deactivate your own account."""
    if state.dry_run:
        print_dry_run("POST", f"users/{id}/deactivate/")
        return
    if not state.yes:
        if not typer.confirm(f"Deactivate user {id}? They will no longer be able to log in.", default=False):
            abort()
    try:
        with _client() as client:
            data = client.post(f"users/{id}/deactivate/")
    except RetailOpsError as e:
        handle_error(e)
        return
    except httpx.ConnectError as e:
        handle_connection_error(e, get_profile(state.profile).base_url)
        return
    print_success(data.get("detail", f"User {id} deactivated."))


@app.command()
def reactivate(
    id: int = typer.Argument(..., help="User ID."),
) -> None:
    """Reactivate a previously deactivated user account (Admin only)."""
    try:
        with _client() as client:
            data = client.post(f"users/{id}/reactivate/")
    except RetailOpsError as e:
        handle_error(e)
        return
    except httpx.ConnectError as e:
        handle_connection_error(e, get_profile(state.profile).base_url)
        return
    print_success(data.get("detail", f"User {id} reactivated."))
