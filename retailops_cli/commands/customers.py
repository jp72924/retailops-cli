"""
commands/customers.py
---------------------
  retailops-cli customers list   [--search TEXT] [--ordering FIELD] [--page N] [--all]
  retailops-cli customers get    <id>
  retailops-cli customers create [field flags]
  retailops-cli customers update <id> [field flags]
  retailops-cli customers delete <id>

Permissions: any authenticated user.
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
def list_customers(
    search:   Optional[str] = typer.Option(None,  "--search",   "-s", help="Search name/email."),
    ordering: Optional[str] = typer.Option(None,  "--ordering", "-O", help="e.g. last_name or -created_at."),
    page:     int            = typer.Option(1,     "--page",     "-p"),
    all_:     bool           = typer.Option(False, "--all",            is_flag=True),
    output:   Optional[str]  = typer.Option(None,  "--output",  "-o"),
) -> None:
    """List customers."""
    fmt    = output or state.output
    params = {"search": search, "ordering": ordering}
    try:
        with _client() as client:
            data = fetch_all(client, "customers/", params) if all_ \
                   else paginated_get(client, "customers/", params, page, state.page_size)
    except RetailOpsError as e:
        handle_error(e)
        return
    except httpx.ConnectError as e:
        handle_connection_error(e, get_profile(state.profile).base_url)
        return
    render(data, fmt, columns=["id", "full_name", "email", "phone", "city", "country", "created_at"])


# ── get ───────────────────────────────────────────────────────────────────────

@app.command()
def get(
    id:     int           = typer.Argument(..., help="Customer ID."),
    output: Optional[str] = typer.Option(None, "--output", "-o"),
) -> None:
    """Retrieve a customer."""
    fmt = output or state.output
    try:
        with _client() as client:
            data = client.get(f"customers/{id}/")
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
    first_name:    str           = typer.Option(...,  "--first-name",    "-f", prompt=True),
    last_name:     str           = typer.Option(...,  "--last-name",     "-l", prompt=True),
    email:         str           = typer.Option(...,  "--email",         "-e", prompt=True),
    phone:         Optional[str] = typer.Option(None, "--phone"),
    national_id:   Optional[str] = typer.Option(None, "--national-id",         help="Unique national / tax ID."),
    dob:           Optional[str] = typer.Option(None, "--dob",                 help="Date of birth (YYYY-MM-DD)."),
    gender:        Optional[str] = typer.Option(None, "--gender",              help="M, F, or empty string to clear."),
    address_line1: Optional[str] = typer.Option(None, "--address"),
    address_line2: Optional[str] = typer.Option(None, "--address-line-2",      help="Apartment, suite, unit, etc."),
    city:          Optional[str] = typer.Option(None, "--city"),
    state_:        Optional[str] = typer.Option(None, "--state",               help="State / province."),
    postal_code:   Optional[str] = typer.Option(None, "--postal-code"),
    country:       Optional[str] = typer.Option(None, "--country",             help="Defaults to 'United States'."),
    notes:         Optional[str] = typer.Option(None, "--notes"),
    user_id:       Optional[int] = typer.Option(None, "--user-id",             help="Optional User account FK to associate."),
    output:        Optional[str] = typer.Option(None, "--output",         "-o"),
) -> None:
    """Create a new customer."""
    fmt = output or state.output
    try:
        with _client() as client:
            data = client.post("customers/", {
                "first_name":    first_name,
                "last_name":     last_name,
                "email":         email,
                "phone":         phone,
                "national_id":   national_id,
                "date_of_birth": dob,
                "gender":        gender,
                "address_line1": address_line1,
                "address_line2": address_line2,
                "city":          city,
                "state":         state_,
                "postal_code":   postal_code,
                "country":       country,
                "notes":         notes,
                "user":          user_id,
            })
    except RetailOpsError as e:
        handle_error(e)
        return
    except httpx.ConnectError as e:
        handle_connection_error(e, get_profile(state.profile).base_url)
        return
    print_success(f"Customer '{data['full_name']}' created (id={data['id']}).")
    render(data, fmt)


# ── update ────────────────────────────────────────────────────────────────────

@app.command()
def update(
    id:            int            = typer.Argument(..., help="Customer ID."),
    first_name:    Optional[str]  = typer.Option(None, "--first-name",     "-f"),
    last_name:     Optional[str]  = typer.Option(None, "--last-name",      "-l"),
    email:         Optional[str]  = typer.Option(None, "--email",          "-e"),
    phone:         Optional[str]  = typer.Option(None, "--phone"),
    national_id:   Optional[str]  = typer.Option(None, "--national-id",         help="Unique national / tax ID."),
    dob:           Optional[str]  = typer.Option(None, "--dob",                 help="Date of birth (YYYY-MM-DD)."),
    gender:        Optional[str]  = typer.Option(None, "--gender",              help="M, F, or empty string to clear."),
    address_line1: Optional[str]  = typer.Option(None, "--address"),
    address_line2: Optional[str]  = typer.Option(None, "--address-line-2",      help="Apartment, suite, unit, etc."),
    city:          Optional[str]  = typer.Option(None, "--city"),
    state_:        Optional[str]  = typer.Option(None, "--state"),
    postal_code:   Optional[str]  = typer.Option(None, "--postal-code"),
    country:       Optional[str]  = typer.Option(None, "--country"),
    notes:         Optional[str]  = typer.Option(None, "--notes"),
    user_id:       Optional[int]  = typer.Option(None, "--user-id",             help="Associated User account FK."),
    output:        Optional[str]  = typer.Option(None, "--output",         "-o"),
) -> None:
    """Update customer fields. Only supplied flags are sent."""
    body: dict = {}
    for key, val in [
        ("first_name",    first_name),    ("last_name",     last_name),
        ("email",         email),         ("phone",         phone),
        ("national_id",   national_id),   ("date_of_birth", dob),
        ("gender",        gender),        ("address_line1", address_line1),
        ("address_line2", address_line2), ("city",          city),
        ("state",         state_),        ("postal_code",   postal_code),
        ("country",       country),       ("notes",         notes),
        ("user",          user_id),
    ]:
        if val is not None:
            body[key] = val
    if not body:
        console.print("[yellow]No fields supplied. Nothing to update.[/yellow]")
        raise typer.Exit(0)
    fmt = output or state.output
    try:
        with _client() as client:
            data = client.patch(f"customers/{id}/", body)
    except RetailOpsError as e:
        handle_error(e)
        return
    except httpx.ConnectError as e:
        handle_connection_error(e, get_profile(state.profile).base_url)
        return
    print_success(f"Customer {id} updated.")
    render(data, fmt)


# ── delete ────────────────────────────────────────────────────────────────────

@app.command()
def delete(
    id: int = typer.Argument(..., help="Customer ID."),
) -> None:
    """Delete a customer. Blocked if the customer has any associated orders."""
    if state.dry_run:
        print_dry_run("DELETE", f"customers/{id}/")
        return
    if not state.yes:
        if not typer.confirm(f"Delete customer {id}? This cannot be undone.", default=False):
            abort()
    try:
        with _client() as client:
            client.delete(f"customers/{id}/")
    except RetailOpsError as e:
        handle_error(e)
        return
    except httpx.ConnectError as e:
        handle_connection_error(e, get_profile(state.profile).base_url)
        return
    print_success(f"Customer {id} deleted.")
