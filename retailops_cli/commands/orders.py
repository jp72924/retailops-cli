"""
commands/orders.py
------------------
Full order CRUD, all lifecycle transitions, and bulk transition operations.

  retailops-cli orders list          [--status STATUS] [--customer INT] [--from DATE] [--to DATE]
                           [--search TEXT] [--page N] [--all]
  retailops-cli orders get           <id>
  retailops-cli orders create        --customer-id INT --items JSON [--discount STR] [--tax STR] [--notes TEXT]
  retailops-cli orders update        <id> [--items JSON] [--discount STR] [--tax STR] [--notes TEXT]
  retailops-cli orders delete        <id>
  retailops-cli orders submit        <id>
  retailops-cli orders confirm       <id>
  retailops-cli orders cancel        <id>
  retailops-cli orders ship          <id>
  retailops-cli orders deliver       <id>
  retailops-cli orders refund        <id>
  retailops-cli orders bulk-confirm  --id INT [--id INT ...]
  retailops-cli orders bulk-ship     --id INT [--id INT ...]
  retailops-cli orders bulk-deliver  --id INT [--id INT ...]

Permissions (enforced server-side):
  create / update / delete / submit / ship / deliver — Staff+
  confirm / cancel / bulk-*                          — Manager+
  refund                                             — Admin only
"""

from __future__ import annotations

import json
from typing import Optional

import httpx
import typer

from typing import List

from .. import state
from ..config import get_profile
from ..errors import RetailOpsError, abort, handle_error, handle_connection_error
from ..output import console, err_console, print_dry_run, print_success, render, render_partial_success
from ..pager import fetch_all, paginated_get

app = typer.Typer(no_args_is_help=True)


def _client():
    from ..client import RetailOpsClient
    return RetailOpsClient(get_profile(state.profile), verbose=state.verbose)


def _parse_items(items_arg: str) -> list:
    """Parse --items into a list. Accepts an inline JSON array, ``@path.json``,
    or ``-`` (stdin). Raises typer.Exit(1) on bad JSON or shape."""
    from ..output import read_json_arg
    parsed = read_json_arg(items_arg, what="--items")
    if not isinstance(parsed, list):
        err_console.print(f"[red]Invalid --items:[/red] expected a JSON array, got {type(parsed).__name__}.")
        err_console.print(
            '[dim]Example: --items \'[{"product_id": 7, "quantity": 2}]\''
        )
        raise typer.Exit(1)
    return parsed


def _transition(id: int, action: str) -> None:
    """POST to a lifecycle transition endpoint and render the result."""
    try:
        with _client() as client:
            data = client.post(f"orders/{id}/{action}/")
    except RetailOpsError as e:
        handle_error(e)
        return
    except httpx.ConnectError as e:
        handle_connection_error(e, get_profile(state.profile).base_url)
        return
    print_success(f"Order {id} → [bold]{data['status']}[/bold].")
    render(data, state.output, columns=[
        "id", "order_number", "status", "customer",
        "total_amount", "amount_paid", "amount_outstanding",
    ])


# ── list ──────────────────────────────────────────────────────────────────────

@app.command(name="list")
def list_orders(
    status:    Optional[str] = typer.Option(None,  "--status",   "-s",
                                             help="draft|pending|confirmed|paid|shipped|delivered|cancelled|refunded"),
    customer:  Optional[int] = typer.Option(None,  "--customer", "-c", help="Filter by customer ID."),
    date_from: Optional[str] = typer.Option(None,  "--from",           help="YYYY-MM-DD"),
    date_to:   Optional[str] = typer.Option(None,  "--to",             help="YYYY-MM-DD"),
    search:    Optional[str] = typer.Option(None,  "--search",         help="Search by order number."),
    ordering:  Optional[str] = typer.Option(None,  "--ordering", "-O"),
    page:      int            = typer.Option(1,     "--page",     "-p"),
    all_:      bool           = typer.Option(False, "--all",            is_flag=True),
    output:    Optional[str]  = typer.Option(None,  "--output",  "-o"),
) -> None:
    """List sales orders."""
    fmt    = output or state.output
    params = {
        "status":    status,
        "customer":  customer,
        "date_from": date_from,
        "date_to":   date_to,
        "search":    search,
        "ordering":  ordering,
    }
    try:
        with _client() as client:
            data = fetch_all(client, "orders/", params) if all_ \
                   else paginated_get(client, "orders/", params, page, state.page_size)
    except RetailOpsError as e:
        handle_error(e)
        return
    except httpx.ConnectError as e:
        handle_connection_error(e, get_profile(state.profile).base_url)
        return
    render(data, fmt, columns=[
        "id", "order_number", "customer", "status",
        "total_amount", "amount_outstanding", "created_at",
    ])


# ── get ───────────────────────────────────────────────────────────────────────

@app.command()
def get(
    id:     int           = typer.Argument(..., help="Order ID."),
    output: Optional[str] = typer.Option(None, "--output", "-o"),
) -> None:
    """Retrieve a full order including line items and payment summary."""
    fmt = output or state.output
    try:
        with _client() as client:
            data = client.get(f"orders/{id}/")
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
    customer_id: int           = typer.Option(...,  "--customer-id", "-c",
                                               prompt=True, help="Customer ID."),
    items:       str           = typer.Option(...,  "--items",       "-i",
                                               help='JSON array: \'[{"product_id":7,"quantity":2}]\'. '
                                                    'Use @path.json to load from a file, or "-" to read from stdin.'),
    discount:    Optional[str] = typer.Option(None, "--discount",         help='Discount amount, e.g. "10.00".'),
    tax:         Optional[str] = typer.Option(None, "--tax",              help='Tax amount, e.g. "5.00".'),
    notes:       Optional[str] = typer.Option(None, "--notes",       "-n"),
    output:      Optional[str] = typer.Option(None, "--output",      "-o"),
) -> None:
    """
    Create a Draft sales order.

    Line items are supplied as a JSON array via --items.
    Each item requires product_id and quantity; unit_price is optional.

    \b
    Example:
      retailops-cli orders create --customer-id 14 \\
        --items '[{"product_id": 7, "quantity": 2}, {"product_id": 12, "quantity": 1}]'
    """
    parsed_items = _parse_items(items)
    fmt          = output or state.output
    try:
        with _client() as client:
            data = client.post("orders/", {
                "customer_id":     customer_id,
                "items":           parsed_items,
                "discount_amount": discount,
                "tax_amount":      tax,
                "notes":           notes,
            })
    except RetailOpsError as e:
        handle_error(e)
        return
    except httpx.ConnectError as e:
        handle_connection_error(e, get_profile(state.profile).base_url)
        return
    print_success(f"Order [bold]{data['order_number']}[/bold] created (id={data['id']}, status=draft).")
    render(data, fmt)


# ── update ────────────────────────────────────────────────────────────────────

@app.command()
def update(
    id:       int            = typer.Argument(..., help="Order ID. Must be in Draft status."),
    items:    Optional[str]  = typer.Option(None, "--items",    "-i",
                                             help='JSON array. Replaces ALL existing line items. '
                                                  'Use @path.json or "-" (stdin) to load.'),
    discount: Optional[str]  = typer.Option(None, "--discount"),
    tax:      Optional[str]  = typer.Option(None, "--tax"),
    notes:    Optional[str]  = typer.Option(None, "--notes",   "-n"),
    output:   Optional[str]  = typer.Option(None, "--output",  "-o"),
) -> None:
    """Update a Draft order. Supplying --items replaces all line items."""
    body: dict = {}
    if items    is not None: body["items"]           = _parse_items(items)
    if discount is not None: body["discount_amount"] = discount
    if tax      is not None: body["tax_amount"]      = tax
    if notes    is not None: body["notes"]           = notes
    if not body:
        console.print("[yellow]No fields supplied. Nothing to update.[/yellow]")
        raise typer.Exit(0)
    fmt = output or state.output
    try:
        with _client() as client:
            data = client.patch(f"orders/{id}/", body)
    except RetailOpsError as e:
        handle_error(e)
        return
    except httpx.ConnectError as e:
        handle_connection_error(e, get_profile(state.profile).base_url)
        return
    print_success(f"Order {id} updated.")
    render(data, fmt)


# ── delete ────────────────────────────────────────────────────────────────────

@app.command()
def delete(
    id: int = typer.Argument(..., help="Order ID. Must be in Draft status."),
) -> None:
    """Permanently delete a Draft order. Cannot be undone."""
    if not state.yes:
        if not typer.confirm(
            f"Delete order {id}? This permanently removes the order and all its line items.",
            default=False,
        ):
            abort()
    try:
        with _client() as client:
            client.delete(f"orders/{id}/")
    except RetailOpsError as e:
        handle_error(e)
        return
    except httpx.ConnectError as e:
        handle_connection_error(e, get_profile(state.profile).base_url)
        return
    print_success(f"Order {id} deleted.")


# ── lifecycle transitions ─────────────────────────────────────────────────────

@app.command()
def submit(id: int = typer.Argument(..., help="Order ID. Must be in Draft status.")) -> None:
    """Advance an order from Draft → Pending (ready for manager review). Requires Staff+."""
    _transition(id, "submit")


@app.command()
def confirm(id: int = typer.Argument(..., help="Order ID. Must be in Pending status.")) -> None:
    """Confirm a Pending order → Confirmed. Deducts stock. Requires Manager+."""
    _transition(id, "confirm")


@app.command()
def ship(id: int = typer.Argument(..., help="Order ID. Must be in Paid status.")) -> None:
    """Mark a Paid order as Shipped. Requires Staff+."""
    _transition(id, "ship")


@app.command()
def deliver(id: int = typer.Argument(..., help="Order ID. Must be in Shipped status.")) -> None:
    """Mark a Shipped order as Delivered (terminal state). Requires Staff+."""
    _transition(id, "deliver")


@app.command()
def cancel(id: int = typer.Argument(..., help="Order ID. Must be in Confirmed status.")) -> None:
    """
    Cancel a Confirmed order and restore stock. Requires Manager+.

    Cannot be used after payment — use `retailops-cli orders refund` for Paid orders.
    """
    if state.dry_run:
        print_dry_run("POST", f"orders/{id}/cancel/")
        return
    if not state.yes:
        if not typer.confirm(
            f"Cancel order {id}? Stock will be restored via inventory movements.",
            default=False,
        ):
            abort()
    _transition(id, "cancel")


@app.command()
def refund(id: int = typer.Argument(..., help="Order ID. Must be in Paid status.")) -> None:
    """
    Refund a Paid order and restore stock. Requires Admin role.

    Payment records are NOT deleted — they remain as immutable financial records.
    This action cannot be undone.
    """
    if state.dry_run:
        print_dry_run("POST", f"orders/{id}/refund/")
        return
    if not state.yes:
        console.print(
            f"[bold red]Refund order {id}?[/bold red] "
            "This is irreversible. Stock will be restored. "
            "Payment records are kept."
        )
        confirm_text = typer.prompt('Type the order ID to confirm')
        if confirm_text.strip() != str(id):
            abort("Confirmation did not match. Refund cancelled.")
    _transition(id, "refund")


# ── bulk transitions ──────────────────────────────────────────────────────────

_BULK_COLUMNS = [
    "id", "order_number", "customer", "status",
    "total_amount", "amount_outstanding",
]


def _bulk_transition(ids: list[int], action: str, fmt: str) -> None:
    """POST to bulk-transition and render the partial-success response."""
    try:
        with _client() as client:
            data = client.post("orders/bulk-transition/", {
                "order_ids": ids,
                "action":    action,
            })
    except RetailOpsError as e:
        handle_error(e)
        return
    except httpx.ConnectError as e:
        handle_connection_error(e, get_profile(state.profile).base_url)
        return
    render_partial_success(data, fmt, succeeded_columns=_BULK_COLUMNS)


@app.command(name="bulk-confirm")
def bulk_confirm(
    ids:    List[int]     = typer.Option(..., "--id", help="Order ID (repeatable): --id 1 --id 2 --id 3"),
    output: Optional[str] = typer.Option(None, "--output", "-o"),
) -> None:
    """
    Confirm multiple Pending orders in one request. Requires Manager role.

    Stock is deducted for each successfully confirmed order. Orders that are
    not in Pending status (or have no line items) appear in the failed list.

    \b
    Example:
      retailops-cli orders bulk-confirm --id 4 --id 7 --id 12
    """
    _bulk_transition(ids, "confirm", output or state.output)


@app.command(name="bulk-ship")
def bulk_ship(
    ids:    List[int]     = typer.Option(..., "--id", help="Order ID (repeatable): --id 1 --id 2 --id 3"),
    output: Optional[str] = typer.Option(None, "--output", "-o"),
) -> None:
    """
    Mark multiple Paid orders as Shipped in one request. Requires Manager role.

    Orders not in Paid status appear in the failed list.

    \b
    Example:
      retailops-cli orders bulk-ship --id 4 --id 7 --id 12
    """
    _bulk_transition(ids, "ship", output or state.output)


@app.command(name="bulk-deliver")
def bulk_deliver(
    ids:    List[int]     = typer.Option(..., "--id", help="Order ID (repeatable): --id 1 --id 2 --id 3"),
    output: Optional[str] = typer.Option(None, "--output", "-o"),
) -> None:
    """
    Mark multiple Shipped orders as Delivered in one request. Requires Manager role.

    Orders not in Shipped status appear in the failed list.

    \b
    Example:
      retailops-cli orders bulk-deliver --id 4 --id 7 --id 12
    """
    _bulk_transition(ids, "deliver", output or state.output)
