"""
commands/settings.py
--------------------
  retailops-cli settings get
  retailops-cli settings update  [--currency-code STR] [--currency-symbol STR]
                       [--decimal-places INT]
                       [--secondary-enabled / --no-secondary-enabled]
                       [--secondary-code STR] [--secondary-symbol STR]
                       [--secondary-decimal-places INT] [--secondary-rate STR]

System-wide currency configuration (primary + optional secondary currency).
Permissions: get = any authenticated; update = Manager+.
"""

from __future__ import annotations

from typing import List, Optional

import httpx
import typer

from .. import state
from ..config import get_profile
from ..errors import RetailOpsError, handle_error, handle_connection_error
from ..output import console, print_success, render

app = typer.Typer(no_args_is_help=True)


def _client():
    from ..client import RetailOpsClient
    return RetailOpsClient(get_profile(state.profile), verbose=state.verbose)


# ── get ───────────────────────────────────────────────────────────────────────

@app.command()
def get(
    output: Optional[str] = typer.Option(None, "--output", "-o"),
) -> None:
    """Show the current system settings."""
    fmt = output or state.output
    try:
        with _client() as client:
            data = client.get("settings/")
    except RetailOpsError as e:
        handle_error(e)
        return
    except httpx.ConnectError as e:
        handle_connection_error(e, get_profile(state.profile).base_url)
        return
    render(data, fmt)


# ── update ────────────────────────────────────────────────────────────────────

@app.command()
def update(
    currency_code:   Optional[str]  = typer.Option(None, "--currency-code",
                                                    help="ISO 4217 code, e.g. USD, EUR, GBP."),
    currency_symbol: Optional[str]  = typer.Option(None, "--currency-symbol",
                                                    help="Display symbol, e.g. $, €, £."),
    decimal_places:  Optional[int]  = typer.Option(None, "--decimal-places",
                                                    help="Decimal places for monetary display (0–4)."),
    secondary_enabled:        Optional[bool] = typer.Option(
        None, "--secondary-enabled/--no-secondary-enabled",
        help="Enable or disable the secondary (local) currency."),
    secondary_code:           Optional[str]  = typer.Option(
        None, "--secondary-code",
        help="Secondary ISO 4217 code, e.g. VES, ARS."),
    secondary_symbol:         Optional[str]  = typer.Option(
        None, "--secondary-symbol",
        help="Secondary display symbol, e.g. 'Bs.'."),
    secondary_decimal_places: Optional[int]  = typer.Option(
        None, "--secondary-decimal-places",
        help="Secondary decimal places (0–4)."),
    secondary_rate:           Optional[str]  = typer.Option(
        None, "--secondary-rate",
        help="Exchange rate (primary to secondary), decimal string e.g. '36.50'."),
    ocr_enabled: Optional[bool] = typer.Option(
        None, "--ocr-enabled/--no-ocr-enabled",
        help="Enable or disable OCR receipt verification."),
    ocr_provider: Optional[str] = typer.Option(None, "--ocr-provider", help="OCR provider name, e.g. vepay."),
    ocr_base_url: Optional[str] = typer.Option(None, "--ocr-base-url", help="OCR provider base URL."),
    ocr_api_key: Optional[str] = typer.Option(None, "--ocr-api-key", help="Set the OCR provider API key."),
    clear_ocr_api_key: bool = typer.Option(False, "--clear-ocr-api-key", help="Clear the stored OCR API key."),
    ocr_timeout_seconds: Optional[int] = typer.Option(None, "--ocr-timeout-seconds"),
    ocr_max_file_mb: Optional[int] = typer.Option(None, "--ocr-max-file-mb"),
    ocr_strict_amount: Optional[bool] = typer.Option(
        None, "--ocr-strict-amount/--no-ocr-strict-amount",
        help="Require OCR amount to match the expected amount."),
    ocr_require_complete: Optional[bool] = typer.Option(
        None, "--ocr-require-complete/--no-ocr-require-complete",
        help="Require VEPay to mark OCR results complete."),
    ocr_enabled_methods: Optional[List[str]] = typer.Option(
        None, "--ocr-enabled-method",
        help="Receipt payment method enabled for OCR. Repeat for multiple values."),
    receipt_image_required: Optional[bool] = typer.Option(
        None, "--receipt-image-required/--no-receipt-image-required",
        help="Require receipt images for mobile payment and bank transfer kiosk payments."),
    delete_receipt_image_after_days: Optional[int] = typer.Option(
        None, "--delete-receipt-image-after-days",
        help="Receipt image retention window in days."),
    output:          Optional[str]  = typer.Option(None, "--output", "-o"),
) -> None:
    """Update system settings. Requires Manager role.

    Primary fields: --currency-code, --currency-symbol, --decimal-places.
    Secondary fields: --secondary-enabled, --secondary-code, --secondary-symbol,
    --secondary-decimal-places, --secondary-rate. OCR fields are also supported.
    Only flags you supply are sent.
    """
    if ocr_api_key is not None and clear_ocr_api_key:
        from ..errors import err_console
        err_console.print("[red]Choose either --ocr-api-key or --clear-ocr-api-key, not both.[/red]")
        raise typer.Exit(1)

    body: dict = {}
    if currency_code            is not None: body["currency_code"]            = currency_code
    if currency_symbol          is not None: body["currency_symbol"]          = currency_symbol
    if decimal_places           is not None: body["decimal_places"]           = decimal_places
    if secondary_enabled        is not None: body["secondary_currency_enabled"]  = secondary_enabled
    if secondary_code           is not None: body["secondary_currency_code"]     = secondary_code
    if secondary_symbol         is not None: body["secondary_currency_symbol"]   = secondary_symbol
    if secondary_decimal_places is not None: body["secondary_decimal_places"]    = secondary_decimal_places
    if secondary_rate           is not None: body["secondary_exchange_rate"]     = secondary_rate
    if ocr_enabled              is not None: body["ocr_enabled"]                 = ocr_enabled
    if ocr_provider             is not None: body["ocr_provider"]                = ocr_provider
    if ocr_base_url             is not None: body["ocr_base_url"]                = ocr_base_url
    if ocr_api_key              is not None: body["ocr_api_key"]                 = ocr_api_key
    if clear_ocr_api_key:                    body["ocr_api_key"]                 = ""
    if ocr_timeout_seconds      is not None: body["ocr_timeout_seconds"]         = ocr_timeout_seconds
    if ocr_max_file_mb          is not None: body["ocr_max_file_mb"]             = ocr_max_file_mb
    if ocr_strict_amount        is not None: body["ocr_strict_amount"]           = ocr_strict_amount
    if ocr_require_complete     is not None: body["ocr_require_complete"]        = ocr_require_complete
    if ocr_enabled_methods      is not None: body["ocr_enabled_methods"]         = ocr_enabled_methods
    if receipt_image_required   is not None:
        body["receipt_image_required_for_receipt_methods"] = receipt_image_required
    if delete_receipt_image_after_days is not None:
        body["delete_receipt_image_after_days"] = delete_receipt_image_after_days

    if not body:
        console.print("[yellow]No fields supplied. Nothing to update.[/yellow]")
        raise typer.Exit(0)

    fmt = output or state.output
    try:
        with _client() as client:
            data = client.patch("settings/", body)
    except RetailOpsError as e:
        handle_error(e)
        return
    except httpx.ConnectError as e:
        handle_connection_error(e, get_profile(state.profile).base_url)
        return
    print_success("Settings updated.")
    render(data, fmt)
