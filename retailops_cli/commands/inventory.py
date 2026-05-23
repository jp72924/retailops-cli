"""
commands/inventory.py
---------------------
  retailops-cli inventory list          [--product INT] [--type TYPE] [--from DATE] [--to DATE]
                              [--page N] [--all]
  retailops-cli inventory get           <id>
  retailops-cli inventory adjust        --product-id INT --quantity INT [--notes TEXT]
  retailops-cli inventory bulk-adjust   --adjustments JSON

Movements are immutable records — no update or delete.
Permissions: list/get = any authenticated; adjust/bulk-adjust = Manager+.
"""

from __future__ import annotations

import json
from typing import Optional

import httpx
import typer

from .. import state
from ..config import get_profile
from ..errors import RetailOpsError, handle_error, handle_connection_error
from ..output import err_console, print_dry_run, print_success, read_json_arg, render, render_partial_success
from ..pager import fetch_all, paginated_get

app = typer.Typer(no_args_is_help=True)


def _client():
    from ..client import RetailOpsClient
    return RetailOpsClient(get_profile(state.profile), verbose=state.verbose)


# ── list ──────────────────────────────────────────────────────────────────────

@app.command(name="list")
def list_movements(
    product:   Optional[int]  = typer.Option(None,  "--product",  "-p", help="Filter by product ID."),
    type_:     Optional[str]  = typer.Option(None,  "--type",     "-t",
                                              help="sale | purchase | adjustment | return"),
    ref_type:  Optional[str]  = typer.Option(None,  "--ref-type",
                                              help="SalesOrder | PurchaseOrder | ManualAdjustment | Return"),
    date_from: Optional[str]  = typer.Option(None,  "--from",           help="YYYY-MM-DD"),
    date_to:   Optional[str]  = typer.Option(None,  "--to",             help="YYYY-MM-DD"),
    ordering:  Optional[str]  = typer.Option(None,  "--ordering", "-O"),
    page:      int             = typer.Option(1,     "--page"),
    all_:      bool            = typer.Option(False, "--all",            is_flag=True),
    output:    Optional[str]   = typer.Option(None,  "--output",  "-o"),
) -> None:
    """List inventory movements (newest first by default)."""
    fmt    = output or state.output
    params = {
        "product":        product,
        "movement_type":  type_,
        "reference_type": ref_type,
        "date_from":      date_from,
        "date_to":        date_to,
        "ordering":       ordering,
    }
    try:
        with _client() as client:
            data = fetch_all(client, "inventory/", params) if all_ \
                   else paginated_get(client, "inventory/", params, page, state.page_size)
    except RetailOpsError as e:
        handle_error(e)
        return
    except httpx.ConnectError as e:
        handle_connection_error(e, get_profile(state.profile).base_url)
        return
    render(data, fmt, columns=[
        "id", "product", "movement_type", "quantity",
        "reference_type", "reference_id", "created_by", "created_at",
    ])


# ── get ───────────────────────────────────────────────────────────────────────

@app.command()
def get(
    id:     int           = typer.Argument(..., help="Movement ID."),
    output: Optional[str] = typer.Option(None, "--output", "-o"),
) -> None:
    """Retrieve a single inventory movement record."""
    fmt = output or state.output
    try:
        with _client() as client:
            data = client.get(f"inventory/{id}/")
    except RetailOpsError as e:
        handle_error(e)
        return
    except httpx.ConnectError as e:
        handle_connection_error(e, get_profile(state.profile).base_url)
        return
    render(data, fmt)


# ── adjust ────────────────────────────────────────────────────────────────────

@app.command()
def adjust(
    product_id: int           = typer.Option(...,  "--product-id", "-p",
                                               prompt=True, help="Product ID to adjust."),
    quantity:   int           = typer.Option(...,  "--quantity",   "-q",
                                               prompt=True,
                                               help="Signed quantity: positive=addition, negative=deduction. Zero rejected."),
    notes:      Optional[str] = typer.Option(None, "--notes",      "-n",
                                               help="Reason for the adjustment."),
    output:     Optional[str] = typer.Option(None, "--output",    "-o"),
) -> None:
    """
    Record a manual stock adjustment. Requires Manager role.

    Use a positive quantity to add stock (e.g. stock received).
    Use a negative quantity to deduct stock (e.g. damaged goods written off).
    Rate limited to 30 requests per minute (shared with bulk-adjust).
    """
    if quantity == 0:
        from ..errors import err_console
        err_console.print("[red]Quantity cannot be zero.[/red]")
        raise typer.Exit(1)

    fmt = output or state.output
    direction = f"[green]+{quantity}[/green]" if quantity > 0 else f"[red]{quantity}[/red]"

    body = {"product_id": product_id, "quantity": quantity, "notes": notes}

    if state.dry_run:
        print_dry_run("POST", "inventory/adjust/", body)
        return

    if not state.yes:
        if not typer.confirm(
            f"Record adjustment of {quantity:+d} units for product {product_id}?",
            default=True,
        ):
            from ..errors import abort
            abort()

    try:
        with _client() as client:
            data = client.post("inventory/adjust/", body)
    except RetailOpsError as e:
        handle_error(e)
        return
    except httpx.ConnectError as e:
        handle_connection_error(e, get_profile(state.profile).base_url)
        return

    print_success(f"Adjustment recorded (movement id={data['id']}, qty={direction}).")
    render(data, fmt)


# ── bulk-adjust ───────────────────────────────────────────────────────────────

_BULK_COLUMNS = [
    "id", "product", "movement_type", "quantity",
    "reference_type", "created_by", "created_at",
]


@app.command(name="bulk-adjust")
def bulk_adjust(
    adjustments: str          = typer.Option(..., "--adjustments", "-a",
                                              help='JSON array of {product_id, quantity, notes?} objects. '
                                                   'Use @path.json to load from a file, or "-" to read from stdin.'),
    output:      Optional[str] = typer.Option(None, "--output", "-o"),
) -> None:
    """
    Record stock adjustments for multiple products in one request. Requires Manager role.

    Each entry in the JSON array must include product_id (int) and quantity (non-zero int).
    notes is optional. Positive quantity adds stock; negative deducts.

    The response uses a partial-success pattern: each product is processed
    independently. Failures are reported without aborting the rest of the batch.
    Rate limited to 30 requests per minute (shared with adjust).

    \b
    Examples:
      retailops-cli inventory bulk-adjust --adjustments '[
        {"product_id": 3, "quantity": 50, "notes": "Weekly restock"},
        {"product_id": 7, "quantity": -5, "notes": "Damaged in transit"}
      ]'
      retailops-cli inventory bulk-adjust --adjustments @restock.json
      cat restock.json | retailops-cli inventory bulk-adjust --adjustments -
    """
    parsed = read_json_arg(adjustments, what="--adjustments")
    try:
        if not isinstance(parsed, list) or not parsed:
            raise ValueError("adjustments must be a non-empty JSON array.")
        for entry in parsed:
            if not isinstance(entry.get("quantity"), int) or entry["quantity"] == 0:
                raise ValueError(
                    f"quantity must be a non-zero integer (product_id={entry.get('product_id', '?')})."
                )
    except ValueError as exc:
        err_console.print(f"[red]Invalid --adjustments:[/red] {exc}")
        err_console.print(
            '[dim]Example: --adjustments \'[{"product_id": 3, "quantity": 50}]\''
        )
        raise typer.Exit(1)

    if state.dry_run:
        print_dry_run("POST", "inventory/bulk-adjust/", {"adjustments": parsed})
        return

    fmt = output or state.output
    try:
        with _client() as client:
            data = client.post("inventory/bulk-adjust/", {"adjustments": parsed})
    except RetailOpsError as e:
        handle_error(e)
        return
    except httpx.ConnectError as e:
        handle_connection_error(e, get_profile(state.profile).base_url)
        return
    render_partial_success(data, fmt, succeeded_columns=_BULK_COLUMNS)
