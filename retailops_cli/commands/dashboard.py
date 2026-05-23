"""
commands/dashboard.py
---------------------
Dashboard command — registered directly on the root app as `retailops-cli dashboard`
(not as a sub-group) because it is a single, top-level command.
"""

from __future__ import annotations

import httpx
import typer

from .. import state
from ..config import get_profile
from ..errors import RetailOpsError, handle_error, handle_connection_error
from ..output import console, render


def dashboard_command(
    output: str = typer.Option(None, "--output", "-o", help="Output format: table | json | csv"),
) -> None:
    """Show the dashboard: monthly stats and recent orders."""
    fmt  = output or state.output
    prof = get_profile(state.profile)

    from ..client import RetailOpsClient
    try:
        with RetailOpsClient(prof, verbose=state.verbose) as client:
            data = client.get("dashboard/")
    except RetailOpsError as e:
        handle_error(e)
        return
    except httpx.ConnectError as e:
        handle_connection_error(e, prof.base_url)
        return

    if fmt == "json":
        render(data, fmt="json")
        return

    # ── summary panel ─────────────────────────────────────────────────────────
    console.print()
    console.print("[bold]Dashboard — This Month[/bold]")
    console.print()
    console.print(f"  Orders this month     : [bold]{data.get('orders_this_month', 0)}[/bold]")
    console.print(f"  Revenue this month    : [bold green]${data.get('revenue_this_month', '0.00')}[/bold green]")
    console.print(f"  Pending payments      : [bold yellow]{data.get('pending_payments_count', 0)}[/bold yellow]")
    console.print(f"  Low / out-of-stock    : [bold red]{data.get('low_stock_count', 0)}[/bold red]")
    console.print()

    # ── recent orders table ───────────────────────────────────────────────────
    recent = data.get("recent_orders", [])
    if recent:
        console.print("[bold]Recent Orders[/bold]")
        render(
            recent,
            fmt="csv" if fmt == "csv" else "table",
            columns=["id", "order_number", "customer", "total_amount", "status", "created_at"],
        )
    else:
        console.print("[dim]No orders yet this month.[/dim]")
