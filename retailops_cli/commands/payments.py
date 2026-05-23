"""
commands/payments.py
--------------------
  retailops-cli payments list   [--order INT] [--method METHOD] [--from DATE] [--to DATE]
                      [--page N] [--all]
  retailops-cli payments get    <id>
  retailops-cli payments record --order INT --amount STR --method METHOD [--ref TEXT] [--notes TEXT]

Payments are immutable financial records — no update or delete.
Permissions: any authenticated user.
"""

from __future__ import annotations

import json
from typing import Optional

import httpx
import typer

from .. import state
from ..config import get_profile
from ..errors import RetailOpsError, handle_error, handle_connection_error
from ..files import multipart_file
from ..output import console, print_dry_run, print_success, read_json_arg, render
from ..pager import fetch_all, paginated_get

app = typer.Typer(no_args_is_help=True)

_METHODS = ["cash", "mobile_payment", "bank_transfer", "card", "check", "other"]
_RECEIPT_METHODS = ["mobile_payment", "bank_transfer"]


def _client():
    from ..client import RetailOpsClient
    return RetailOpsClient(get_profile(state.profile), verbose=state.verbose)


# ── list ──────────────────────────────────────────────────────────────────────

@app.command(name="list")
def list_payments(
    order:     Optional[int] = typer.Option(None,  "--order",    "-o", help="Filter by order ID."),
    method:    Optional[str] = typer.Option(None,  "--payment-method", "--method", "-m",
                                             help="cash | mobile_payment | bank_transfer | card | check | other"),
    status_:   Optional[str] = typer.Option(None,  "--status",
                                             help="confirmed | pending_review"),
    has_receipt: Optional[bool] = typer.Option(None, "--has-receipt/--no-receipt",
                                               help="Filter payments with or without receipt images."),
    bank:      Optional[str] = typer.Option(None, "--bank", help="Filter by origin or recipient bank text."),
    date_from: Optional[str] = typer.Option(None,  "--from",           help="YYYY-MM-DD"),
    date_to:   Optional[str] = typer.Option(None,  "--to",             help="YYYY-MM-DD"),
    ordering:  Optional[str] = typer.Option(None,  "--ordering",  "-O"),
    page:      int            = typer.Option(1,     "--page",      "-p"),
    all_:      bool           = typer.Option(False, "--all",             is_flag=True),
    output:    Optional[str]  = typer.Option(None,  "--output"),
) -> None:
    """List payment records (newest first by default)."""
    fmt    = output or state.output
    params = {
        "sales_order":    order,
        "payment_method": method,
        "status":         status_,
        "has_receipt":    has_receipt,
        "bank":           bank,
        "date_from":      date_from,
        "date_to":        date_to,
        "ordering":       ordering,
    }
    try:
        with _client() as client:
            data = fetch_all(client, "payments/", params) if all_ \
                   else paginated_get(client, "payments/", params, page, state.page_size)
    except RetailOpsError as e:
        handle_error(e)
        return
    except httpx.ConnectError as e:
        handle_connection_error(e, get_profile(state.profile).base_url)
        return
    render(data, fmt, columns=[
        "id", "payment_number", "sales_order_number",
        "amount", "payment_method", "status", "reference_number",
        "recorded_by_name", "created_at",
    ])


# ── get ───────────────────────────────────────────────────────────────────────

@app.command()
def get(
    id:     int           = typer.Argument(..., help="Payment ID."),
    output: Optional[str] = typer.Option(None, "--output", "-o"),
) -> None:
    """Retrieve a single payment record."""
    fmt = output or state.output
    try:
        with _client() as client:
            data = client.get(f"payments/{id}/")
    except RetailOpsError as e:
        handle_error(e)
        return
    except httpx.ConnectError as e:
        handle_connection_error(e, get_profile(state.profile).base_url)
        return
    render(data, fmt)


# ── record ────────────────────────────────────────────────────────────────────

@app.command()
def record(
    order:  int           = typer.Option(...,  "--order",  "-o",
                                          prompt=True, help="Order ID (must be in Confirmed status)."),
    amount: str           = typer.Option(...,  "--amount", "-a",
                                          prompt=True, help='Payment amount, e.g. "150.00".'),
    method: str           = typer.Option(...,  "--method", "-m",
                                          prompt=True,
                                          help="cash | mobile_payment | bank_transfer | card | check | other"),
    ref:    Optional[str] = typer.Option(None, "--ref",          help="External transaction reference."),
    status_: Optional[str] = typer.Option(None, "--status", help="confirmed | pending_review"),
    transaction_key: Optional[str] = typer.Option(None, "--transaction-key", help="Verified receipt transaction key."),
    origin_phone: Optional[str] = typer.Option(None, "--origin-phone"),
    origin_bank: Optional[str] = typer.Option(None, "--origin-bank"),
    recipient_bank: Optional[str] = typer.Option(None, "--recipient-bank"),
    recipient_account: Optional[str] = typer.Option(None, "--recipient-account"),
    receipt_image: Optional[str] = typer.Option(None, "--receipt-image", help="Path to a receipt image to upload."),
    ocr_data: Optional[str] = typer.Option(None, "--ocr-data", help="OCR JSON, @file.json, or - for stdin."),
    notes:  Optional[str] = typer.Option(None, "--notes",  "-n"),
    output: Optional[str] = typer.Option(None, "--output"),
) -> None:
    """
    Record a payment against a Confirmed order.

    If the running total meets or exceeds the order total, the order
    automatically transitions to Paid.
    """
    if method not in _METHODS:
        from ..errors import err_console
        err_console.print(
            f"[red]Invalid payment method '{method}'.[/red] "
            f"Choose from: {', '.join(_METHODS)}"
        )
        raise typer.Exit(1)

    fmt = output or state.output
    parsed_ocr = read_json_arg(ocr_data, what="--ocr-data") if ocr_data else None
    body = {
        "sales_order":       order,
        "amount":            amount,
        "payment_method":    method,
        "status":            status_,
        "reference_number":  ref,
        "transaction_key":   transaction_key,
        "origin_phone":      origin_phone,
        "origin_bank":       origin_bank,
        "recipient_bank":    recipient_bank,
        "recipient_account": recipient_account,
        "ocr_receipt_data":  parsed_ocr,
        "notes":             notes,
    }

    if state.dry_run:
        preview = dict(body)
        if receipt_image:
            preview["receipt_image"] = receipt_image
        print_dry_run("POST", "payments/", preview)
        return

    try:
        with _client() as client:
            if receipt_image:
                form_body = dict(body)
                if parsed_ocr is not None:
                    form_body["ocr_receipt_data"] = json.dumps(parsed_ocr)
                with multipart_file("receipt_image", receipt_image, label="receipt image") as files:
                    data = client.post_multipart("payments/", form_body, files)
            else:
                data = client.post("payments/", body)
    except RetailOpsError as e:
        handle_error(e)
        return
    except httpx.ConnectError as e:
        handle_connection_error(e, get_profile(state.profile).base_url)
        return

    print_success(
        f"Payment [bold]{data['payment_number']}[/bold] recorded "
        f"(${data['amount']} via {data['payment_method']})."
    )

    # Surface the auto-transition to Paid if it happened.
    order_data = data.get("sales_order")
    if isinstance(order_data, dict) and order_data.get("status") == "paid":
        console.print("[green]Order has been fully paid and transitioned to Paid status.[/green]")

    render(data, fmt)


@app.command(name="verify-receipt")
def verify_receipt(
    image: str = typer.Option(..., "--image", "-i", help="Path to the receipt image."),
    method: str = typer.Option(..., "--method", "-m", help="mobile_payment | bank_transfer"),
    sales_order: Optional[int] = typer.Option(None, "--sales-order", "-o", help="Sales order ID."),
    expected_amount_usd: Optional[str] = typer.Option(None, "--expected-amount-usd", help="Expected USD amount when verifying without an order."),
    expected_reference: Optional[str] = typer.Option(None, "--expected-reference"),
    expected_paid_on: Optional[str] = typer.Option(None, "--expected-paid-on", help="YYYY-MM-DD"),
    expected_origin_bank: Optional[str] = typer.Option(None, "--expected-origin-bank"),
    output: Optional[str] = typer.Option(None, "--output"),
) -> None:
    """Verify a mobile-payment or bank-transfer receipt through the API OCR provider."""
    if method not in _RECEIPT_METHODS:
        from ..errors import err_console
        err_console.print(
            f"[red]Invalid receipt method '{method}'.[/red] "
            f"Choose from: {', '.join(_RECEIPT_METHODS)}"
        )
        raise typer.Exit(1)
    if sales_order is None and expected_amount_usd is None:
        from ..errors import err_console
        err_console.print(
            "[red]Expected amount required.[/red] Provide --sales-order or --expected-amount-usd."
        )
        raise typer.Exit(1)

    body = {
        "payment_method": method,
        "sales_order": sales_order,
        "expected_amount_usd": expected_amount_usd,
        "expected_reference": expected_reference,
        "expected_paid_on": expected_paid_on,
        "expected_origin_bank": expected_origin_bank,
    }
    fmt = output or state.output
    try:
        with _client() as client:
            with multipart_file("image", image, label="receipt image") as files:
                data = client.post_multipart("payments/receipts/verify/", body, files)
    except RetailOpsError as e:
        handle_error(e)
        return
    except httpx.ConnectError as e:
        handle_connection_error(e, get_profile(state.profile).base_url)
        return

    render(data, fmt)


@app.command(name="receipt-healthz")
def receipt_healthz(
    output: Optional[str] = typer.Option(None, "--output"),
) -> None:
    """Check OCR provider health through the RetailOps API."""
    fmt = output or state.output
    try:
        with _client() as client:
            data = client.get("payments/receipts/healthz/")
    except RetailOpsError as e:
        handle_error(e)
        return
    except httpx.ConnectError as e:
        handle_connection_error(e, get_profile(state.profile).base_url)
        return

    render(data, fmt)
