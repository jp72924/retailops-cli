"""
commands/recipient_profiles.py
------------------------------
  retailops-cli recipient-profiles list   [--method METHOD] [--active/--inactive]
                                          [--search TEXT] [--ordering FIELD] [--page N] [--all]
  retailops-cli recipient-profiles get    <id>
  retailops-cli recipient-profiles create --method METHOD --bank BANK --document-id ID
                                          [--phone PHONE] [--account-number NUM] [--label TEXT]
  retailops-cli recipient-profiles update <id> [field flags]
  retailops-cli recipient-profiles delete <id>

Recipient profiles are the allowlist that OCR-verified mobile-payment and
bank-transfer receipts are matched against. A receipt only matches when the
identifying field, the bank, and the document ID all agree.

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
    "phone", "account_number", "is_active", "created_at",
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
    output:         Optional[str] = typer.Option(None, "--output",         "-o"),
) -> None:
    """
    Create a recipient profile. Requires Manager role.

    Which identifier you supply depends on the method: mobile_payment needs
    --phone and rejects --account-number; bank_transfer needs --account-number
    and rejects --phone. The server enforces this pairing.

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
    output:         Optional[str]  = typer.Option(None, "--output",         "-o"),
) -> None:
    """Update a recipient profile. Requires Manager role. Only supplied flags are sent."""
    _check_method(method)
    body: dict = {}
    for key, val in [
        ("payment_method", method),      ("bank",       bank),
        ("document_id",    document_id), ("phone",      phone),
        ("account_number", account_number), ("label",   label),
        ("is_active",      active),
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
