"""
commands/kiosk.py
-----------------
Operational helpers for the kiosk API namespace.
"""

from __future__ import annotations

import os
from dataclasses import replace
from typing import Optional

import httpx
import typer

from .. import state
from ..config import get_profile
from ..errors import RetailOpsError, handle_connection_error, handle_error
from ..output import err_console, print_dry_run, render, read_json_arg

app = typer.Typer(no_args_is_help=True)


def _kiosk_client(kiosk_key: str | None):
    key = kiosk_key or os.environ.get("RETAILOPS_KIOSK_API_KEY", "")
    if not key:
        err_console.print(
            "[red]Missing kiosk key.[/red] Pass --kiosk-key or set RETAILOPS_KIOSK_API_KEY."
        )
        raise typer.Exit(2)

    from ..client import RetailOpsClient

    prof = replace(get_profile(state.profile), token=key)
    return RetailOpsClient(prof, verbose=state.verbose, auth_scheme="KioskKey")


def _handle_connection(exc: Exception) -> None:
    handle_connection_error(exc, get_profile(state.profile).base_url)


def _parse_object(raw: str | None, *, what: str) -> dict:
    if not raw:
        return {}
    parsed = read_json_arg(raw, what=what)
    if not isinstance(parsed, dict):
        err_console.print(f"[red]Invalid {what}:[/red] expected a JSON object.")
        raise typer.Exit(1)
    return parsed


def _parse_items(raw: str) -> list:
    parsed = read_json_arg(raw, what="--items")
    if not isinstance(parsed, list) or not parsed:
        err_console.print("[red]Invalid --items:[/red] expected a non-empty JSON array.")
        raise typer.Exit(1)
    return parsed


@app.command()
def identify(
    national_id: str = typer.Option(..., "--national-id", "-n", prompt=True),
    kiosk_key: Optional[str] = typer.Option(None, "--kiosk-key", envvar="RETAILOPS_KIOSK_API_KEY"),
    output: Optional[str] = typer.Option(None, "--output", "-o"),
) -> None:
    """Look up a kiosk customer by national ID."""
    fmt = output or state.output
    try:
        with _kiosk_client(kiosk_key) as client:
            data = client.post("kiosk/identify/", {"national_id": national_id})
    except RetailOpsError as e:
        handle_error(e)
        return
    except httpx.ConnectError as e:
        _handle_connection(e)
        return
    render(data, fmt)


@app.command()
def register(
    national_id: str = typer.Option(..., "--national-id"),
    first_name: str = typer.Option(..., "--first-name"),
    last_name: str = typer.Option(..., "--last-name"),
    email: str = typer.Option(..., "--email"),
    phone: str = typer.Option(..., "--phone"),
    date_of_birth: str = typer.Option(..., "--date-of-birth", help="YYYY-MM-DD"),
    gender: str = typer.Option(..., "--gender", help="M | F"),
    state_: str = typer.Option(..., "--state", help="State / province."),
    city: str = typer.Option(..., "--city"),
    kiosk_key: Optional[str] = typer.Option(None, "--kiosk-key", envvar="RETAILOPS_KIOSK_API_KEY"),
    output: Optional[str] = typer.Option(None, "--output", "-o"),
) -> None:
    """Register a new kiosk customer."""
    body = {
        "national_id": national_id,
        "first_name": first_name,
        "last_name": last_name,
        "email": email,
        "phone": phone,
        "date_of_birth": date_of_birth,
        "gender": gender,
        "state": state_,
        "city": city,
    }
    fmt = output or state.output
    try:
        with _kiosk_client(kiosk_key) as client:
            data = client.post("kiosk/register/", body)
    except RetailOpsError as e:
        handle_error(e)
        return
    except httpx.ConnectError as e:
        _handle_connection(e)
        return
    render(data, fmt)


@app.command(name="products")
def products(
    search: Optional[str] = typer.Option(None, "--search", "-s"),
    kiosk_key: Optional[str] = typer.Option(None, "--kiosk-key", envvar="RETAILOPS_KIOSK_API_KEY"),
    output: Optional[str] = typer.Option(None, "--output", "-o"),
) -> None:
    """Search active kiosk products."""
    fmt = output or state.output
    try:
        with _kiosk_client(kiosk_key) as client:
            data = client.get("kiosk/products/", {"search": search})
    except RetailOpsError as e:
        handle_error(e)
        return
    except httpx.ConnectError as e:
        _handle_connection(e)
        return
    render(data, fmt, columns=["id", "sku", "name", "unit_price", "current_stock", "image_url"])


@app.command(name="product-get")
def product_get(
    id: int = typer.Argument(..., help="Product ID."),
    kiosk_key: Optional[str] = typer.Option(None, "--kiosk-key", envvar="RETAILOPS_KIOSK_API_KEY"),
    output: Optional[str] = typer.Option(None, "--output", "-o"),
) -> None:
    """Fetch one active kiosk product by ID."""
    fmt = output or state.output
    try:
        with _kiosk_client(kiosk_key) as client:
            data = client.get(f"kiosk/products/{id}/")
    except RetailOpsError as e:
        handle_error(e)
        return
    except httpx.ConnectError as e:
        _handle_connection(e)
        return
    render(data, fmt)


@app.command(name="product-lookup")
def product_lookup(
    sku: str = typer.Argument(..., help="Product SKU / barcode."),
    kiosk_key: Optional[str] = typer.Option(None, "--kiosk-key", envvar="RETAILOPS_KIOSK_API_KEY"),
    output: Optional[str] = typer.Option(None, "--output", "-o"),
) -> None:
    """Fetch one active kiosk product by SKU."""
    fmt = output or state.output
    try:
        with _kiosk_client(kiosk_key) as client:
            data = client.get(f"kiosk/product/{sku}/")
    except RetailOpsError as e:
        handle_error(e)
        return
    except httpx.ConnectError as e:
        _handle_connection(e)
        return
    render(data, fmt)


@app.command()
def checkout(
    customer_id: int = typer.Option(..., "--customer-id", "-c"),
    items: str = typer.Option(..., "--items", "-i", help="JSON array, @file.json, or - for stdin."),
    payment_reference: str = typer.Option(..., "--payment-reference", "-r"),
    payment_method: str = typer.Option("card", "--payment-method", "-m"),
    receipt: Optional[str] = typer.Option(None, "--receipt", help="Receipt JSON object, @file.json, or - for stdin."),
    kiosk_key: Optional[str] = typer.Option(None, "--kiosk-key", envvar="RETAILOPS_KIOSK_API_KEY"),
    output: Optional[str] = typer.Option(None, "--output", "-o"),
) -> None:
    """Create a kiosk checkout order and payment."""
    parsed_items = _parse_items(items)
    parsed_receipt = _parse_object(receipt, what="--receipt")
    body = {
        "customer_id": customer_id,
        "items": parsed_items,
        "payment_reference": payment_reference,
        "payment_method": payment_method,
        "receipt": parsed_receipt,
    }
    if state.dry_run:
        print_dry_run("POST", "kiosk/checkout/", body)
        return
    fmt = output or state.output
    try:
        with _kiosk_client(kiosk_key) as client:
            data = client.post("kiosk/checkout/", body)
    except RetailOpsError as e:
        handle_error(e)
        return
    except httpx.ConnectError as e:
        _handle_connection(e)
        return
    render(data, fmt)


@app.command()
def receipt(
    order_id: int = typer.Argument(..., help="Order ID."),
    kiosk_key: Optional[str] = typer.Option(None, "--kiosk-key", envvar="RETAILOPS_KIOSK_API_KEY"),
    output: Optional[str] = typer.Option(None, "--output", "-o"),
) -> None:
    """Retrieve a kiosk receipt for an order created by the station service user."""
    fmt = output or state.output
    try:
        with _kiosk_client(kiosk_key) as client:
            data = client.get(f"kiosk/receipt/{order_id}/")
    except RetailOpsError as e:
        handle_error(e)
        return
    except httpx.ConnectError as e:
        _handle_connection(e)
        return
    render(data, fmt)


@app.command()
def heartbeat(
    kiosk_key: Optional[str] = typer.Option(None, "--kiosk-key", envvar="RETAILOPS_KIOSK_API_KEY"),
    output: Optional[str] = typer.Option(None, "--output", "-o"),
) -> None:
    """Send a kiosk heartbeat."""
    fmt = output or state.output
    try:
        with _kiosk_client(kiosk_key) as client:
            data = client.post("kiosk/heartbeat/")
    except RetailOpsError as e:
        handle_error(e)
        return
    except httpx.ConnectError as e:
        _handle_connection(e)
        return
    render(data, fmt)
