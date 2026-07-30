"""
commands/recipient_profiles.py
------------------------------
  retailops-cli recipient-profiles list   [--method METHOD] [--active/--inactive]
                                          [--primary/--no-primary]
                                          [--search TEXT] [--ordering FIELD] [--page N] [--all]
  retailops-cli recipient-profiles get    <id>
  retailops-cli recipient-profiles create --method METHOD --bank BANK --document-id ID
                                          [--phone PHONE] [--account-number NUM] [--label TEXT]
                                          [--primary/--no-primary]
  retailops-cli recipient-profiles update <id> [field flags] [--primary/--no-primary]
  retailops-cli recipient-profiles delete <id>

Recipient profiles are the allowlist that OCR-verified mobile-payment and
bank-transfer receipts are matched against. A receipt only matches when the
identifying field, the bank, and the document ID all agree.

At most one profile per payment method may be primary — the one customer-
facing systems (the kiosk, for one) show when several are registered.
--primary on create or update auto-demotes whichever other profile of the
same method currently holds it, in the same request; there is no separate
unset step. A method's only profile is always its primary one, applied by
the server automatically on create and again if a delete leaves one behind
— --primary only needs passing once a method has two or more profiles.
Deleting the primary while others remain does not auto-promote a
replacement: zero primaries is a valid, unforced state until someone picks
one with update --primary.

Permissions: Manager+ for every operation, including list and get — these
records carry bank-account and document identifiers used for fraud control,
not general catalog data.
"""

from __future__ import annotations

from typing import Optional

import httpx
import typer

from .. import state
from ..config import get_profile
from ..errors import RetailOpsError, confirm_or_abort, handle_error, handle_connection_error
from ..output import console, err_console, print_success, render
from ..pager import fetch_all, paginated_get

app = typer.Typer(no_args_is_help=True)

_PATH = "payment-recipient-profiles/"

_METHODS = ("mobile_payment", "bank_transfer")

_COLUMNS = [
    "id", "label", "payment_method", "bank",
    "phone", "account_number", "is_active", "is_primary", "created_at",
]


def _client():
    from ..client import RetailOpsClient
    return RetailOpsClient(get_profile(state.profile), verbose=state.verbose)


def _check_method(method: str | None) -> None:
    """Reject an unknown --method before spending a round-trip on it."""
    if method is not None and method not in _METHODS:
        err_console.print(
            f"[red]Invalid --method:[/red] {method!r}. Expected one of: {', '.join(_METHODS)}."
        )
        raise typer.Exit(1)


# ── list ──────────────────────────────────────────────────────────────────────

@app.command(name="list")
def list_profiles(
    method:   Optional[str]  = typer.Option(None,  "--method",   "-m",
                                             help="mobile_payment | bank_transfer"),
    active:   Optional[bool] = typer.Option(None,  "--active/--inactive",
                                             help="Filter by active state."),
    primary:  Optional[bool] = typer.Option(None,  "--primary/--no-primary",
                                             help="Filter by primary status for its payment method."),
    search:   Optional[str]  = typer.Option(None,  "--search",   "-s",
                                             help="Search label, phone, account number, bank, document ID."),
    ordering: Optional[str]  = typer.Option(None,  "--ordering", "-O",
                                             help="e.g. label or -created_at."),
    page:     int             = typer.Option(1,     "--page",     "-p"),
    all_:     bool            = typer.Option(False, "--all",            is_flag=True),
    output:   Optional[str]   = typer.Option(None,  "--output",  "-o"),
) -> None:
    """List recipient profiles. Requires Manager role."""
    _check_method(method)
    fmt    = output or state.output
    params = {
        "payment_method": method,
        "is_active":      active,
        "is_primary":     primary,
        "search":         search,
        "ordering":       ordering,
    }
    try:
        with _client() as client:
            data = fetch_all(client, _PATH, params) if all_ \
                   else paginated_get(client, _PATH, params, page, state.page_size)
    except RetailOpsError as e:
        handle_error(e)
        return
    except httpx.RequestError as e:
        handle_connection_error(e, get_profile(state.profile).base_url)
        return
    render(data, fmt, columns=_COLUMNS)


# ── get ───────────────────────────────────────────────────────────────────────

@app.command()
def get(
    id:     int           = typer.Argument(..., help="Recipient profile ID."),
    output: Optional[str] = typer.Option(None, "--output", "-o"),
) -> None:
    """Retrieve a recipient profile. Requires Manager role."""
    fmt = output or state.output
    try:
        with _client() as client:
            data = client.get(f"{_PATH}{id}/")
    except RetailOpsError as e:
        handle_error(e)
        return
    except httpx.RequestError as e:
        handle_connection_error(e, get_profile(state.profile).base_url)
        return
    render(data, fmt)


# ── create ────────────────────────────────────────────────────────────────────

@app.command()
def create(
    method:         str           = typer.Option(...,  "--method",         "-m", prompt=True,
                                                  help="mobile_payment | bank_transfer"),
    bank:           str           = typer.Option(...,  "--bank",           "-b", prompt=True,
                                                  help="Bank name as it appears on receipts."),
    document_id:    str           = typer.Option(...,  "--document-id",    "-d", prompt=True,
                                                  help="Recipient document / tax ID."),
    phone:          Optional[str] = typer.Option(None, "--phone",
                                                  help="Required for mobile_payment; leave unset for bank_transfer."),
    account_number: Optional[str] = typer.Option(None, "--account-number",
                                                  help="Required for bank_transfer; leave unset for mobile_payment."),
    label:          Optional[str] = typer.Option(None, "--label",          "-l",
                                                  help="Human-friendly name for this profile."),
    active:         bool          = typer.Option(True, "--active/--inactive"),
    primary:        bool          = typer.Option(False, "--primary/--no-primary",
                                                  help="Make this the primary profile for --method. "
                                                       "Automatic when it's the method's only profile."),
    output:         Optional[str] = typer.Option(None, "--output",         "-o"),
) -> None:
    """
    Create a recipient profile. Requires Manager role.

    Which identifier you supply depends on the method: mobile_payment needs
    --phone and rejects --account-number; bank_transfer needs --account-number
    and rejects --phone. The server enforces this pairing.

    If this is the only profile for --method, the server marks it primary
    regardless of --primary/--no-primary. Once a second profile exists for
    the same method, --primary auto-demotes whichever one currently holds it.

    \b
    Example:
      retailops-cli recipient-profiles create --method mobile_payment \\
        --phone 04121234567 --bank BDV --document-id V12345678 --label "Main line"
    """
    _check_method(method)
    fmt = output or state.output
    try:
        with _client() as client:
            data = client.post(_PATH, {
                "payment_method": method,
                "bank":           bank,
                "document_id":    document_id,
                "phone":          phone,
                "account_number": account_number,
                "label":          label,
                "is_active":      active,
                "is_primary":     primary,
            })
    except RetailOpsError as e:
        handle_error(e)
        return
    except httpx.RequestError as e:
        handle_connection_error(e, get_profile(state.profile).base_url)
        return
    print_success(f"Recipient profile created (id={data['id']}, {data['payment_method']}).")
    render(data, fmt)


# ── update ────────────────────────────────────────────────────────────────────

@app.command()
def update(
    id:             int            = typer.Argument(..., help="Recipient profile ID."),
    method:         Optional[str]  = typer.Option(None, "--method",         "-m",
                                                   help="mobile_payment | bank_transfer"),
    bank:           Optional[str]  = typer.Option(None, "--bank",           "-b"),
    document_id:    Optional[str]  = typer.Option(None, "--document-id",    "-d"),
    phone:          Optional[str]  = typer.Option(None, "--phone"),
    account_number: Optional[str]  = typer.Option(None, "--account-number"),
    label:          Optional[str]  = typer.Option(None, "--label",          "-l"),
    active:         Optional[bool] = typer.Option(None, "--active/--inactive"),
    primary:        Optional[bool] = typer.Option(None, "--primary/--no-primary",
                                                   help="--primary auto-demotes whichever other "
                                                        "profile of the same payment method "
                                                        "currently holds it."),
    output:         Optional[str]  = typer.Option(None, "--output",         "-o"),
) -> None:
    """
    Update a recipient profile. Requires Manager role. Only supplied flags are sent.

    --no-primary on the current primary is allowed and leaves the method with
    zero primaries if others remain — nothing is auto-promoted in its place.
    """
    _check_method(method)
    body: dict = {}
    for key, val in [
        ("payment_method", method),      ("bank",       bank),
        ("document_id",    document_id), ("phone",      phone),
        ("account_number", account_number), ("label",   label),
        ("is_active",      active),      ("is_primary", primary),
    ]:
        if val is not None:
            body[key] = val
    if not body:
        console.print("[yellow]No fields supplied. Nothing to update.[/yellow]")
        raise typer.Exit(0)
    fmt = output or state.output
    try:
        with _client() as client:
            data = client.patch(f"{_PATH}{id}/", body)
    except RetailOpsError as e:
        handle_error(e)
        return
    except httpx.RequestError as e:
        handle_connection_error(e, get_profile(state.profile).base_url)
        return
    print_success(f"Recipient profile {id} updated.")
    render(data, fmt)


# ── delete ────────────────────────────────────────────────────────────────────

@app.command()
def delete(
    id: int = typer.Argument(..., help="Recipient profile ID."),
) -> None:
    """
    Delete a recipient profile. Requires Manager role.

    Receipts will stop matching against it immediately. To keep the record but
    take it out of matching, use --inactive on update instead.

    If this was the method's only remaining profile, deleting it leaves that
    method with none — nothing is auto-promoted. If it was the primary among
    several, the method is left with zero primaries until you set one with
    update --primary.
    """
    confirm_or_abort(f"Delete recipient profile {id}? Receipts will no longer match it.")
    try:
        with _client() as client:
            client.delete(f"{_PATH}{id}/")
    except RetailOpsError as e:
        handle_error(e)
        return
    except httpx.RequestError as e:
        handle_connection_error(e, get_profile(state.profile).base_url)
        return
    print_success(f"Recipient profile {id} deleted.")
