"""
commands/products.py
--------------------
  retailops-cli products list      [--category INT] [--stock out|low|ok|all] [--unit UOM]
                         [--active|--inactive] [--search TEXT] [--ordering FIELD]
                         [--page N] [--all]
  retailops-cli products get       <id>
  retailops-cli products create    [field flags]
  retailops-cli products update    <id> [field flags]
  retailops-cli products delete    <id>
  retailops-cli products movements <id> [--page N] [--all]

Permissions: read = any authenticated; write = Manager+.
"""

from __future__ import annotations

from typing import Optional

import httpx
import typer

from .. import state
from ..config import get_profile
from ..errors import RetailOpsError, abort, handle_error, handle_connection_error
from ..files import multipart_file
from ..output import console, print_success, render
from ..pager import fetch_all, paginated_get

app = typer.Typer(no_args_is_help=True)


def _client():
    from ..client import RetailOpsClient
    return RetailOpsClient(get_profile(state.profile), verbose=state.verbose)


# ── list ──────────────────────────────────────────────────────────────────────

@app.command(name="list")
def list_products(
    category: Optional[int]  = typer.Option(None,  "--category", "-c", help="Filter by category ID."),
    stock:    Optional[str]  = typer.Option(None,  "--stock",          help="out | low | ok | all"),
    unit:     Optional[str]  = typer.Option(None,  "--unit",     "-u",
                                            help="Filter by unit_of_measure: piece | kg | liter | meter | box | pack."),
    active:   Optional[bool] = typer.Option(None,  "--active/--inactive",
                                            help="Filter by is_active. Omit for all statuses."),
    search:   Optional[str]  = typer.Option(None,  "--search",   "-s"),
    ordering: Optional[str]  = typer.Option(None,  "--ordering", "-O", help="e.g. name or -unit_price"),
    page:     int             = typer.Option(1,     "--page",     "-p"),
    all_:     bool            = typer.Option(False, "--all",            is_flag=True),
    output:   Optional[str]   = typer.Option(None,  "--output",  "-o"),
) -> None:
    """List products. Omit --active/--inactive to include all statuses."""
    fmt    = output or state.output
    params = {
        "category":        category,
        "stock":           stock,
        "unit_of_measure": unit,
        "is_active":       active,
        "search":          search,
        "ordering":        ordering,
    }
    try:
        with _client() as client:
            data = fetch_all(client, "products/", params) if all_ \
                   else paginated_get(client, "products/", params, page, state.page_size)
    except RetailOpsError as e:
        handle_error(e)
        return
    except httpx.ConnectError as e:
        handle_connection_error(e, get_profile(state.profile).base_url)
        return
    render(data, fmt, columns=[
        "id", "sku", "name", "category", "unit_price",
        "current_stock", "has_image", "is_active", "created_at",
    ])


# ── get ───────────────────────────────────────────────────────────────────────

@app.command()
def get(
    id:     int           = typer.Argument(..., help="Product ID."),
    output: Optional[str] = typer.Option(None, "--output", "-o"),
) -> None:
    """Retrieve a single product including stock levels."""
    fmt = output or state.output
    try:
        with _client() as client:
            data = client.get(f"products/{id}/")
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
    sku:             str           = typer.Option(...,  "--sku",             "-S", prompt=True, help="Stock-keeping unit (unique)."),
    name:            str           = typer.Option(...,  "--name",            "-n", prompt=True),
    category_id:     int           = typer.Option(...,  "--category-id",     "-c", prompt=True),
    unit_of_measure: str           = typer.Option(...,  "--unit",            "-u", prompt=True,
                                                   help="piece | kg | liter | meter | box | pack"),
    unit_price:      str           = typer.Option(...,  "--price",           "-p", prompt=True, help="e.g. 9.99"),
    description:     Optional[str] = typer.Option(None, "--description",     "-d"),
    threshold:       Optional[int] = typer.Option(None, "--low-stock",              help="Low-stock alert threshold. Default: 10."),
    image:           Optional[str] = typer.Option(None, "--image", help="Path to a product image to upload."),
    external_image_url: Optional[str] = typer.Option(None, "--external-image-url", help="External product image URL."),
    is_active:       bool          = typer.Option(True, "--active/--inactive"),
    output:          Optional[str] = typer.Option(None, "--output",         "-o"),
) -> None:
    """Create a new product. Requires Manager role."""
    fmt = output or state.output
    body = {
        "sku":               sku,
        "name":              name,
        "category_id":       category_id,
        "unit_of_measure":   unit_of_measure,
        "unit_price":        unit_price,
        "description":       description,
        "low_stock_threshold": threshold,
        "external_image_url": external_image_url,
        "is_active":         is_active,
    }
    try:
        with _client() as client:
            if image:
                with multipart_file("image", image, label="product image") as files:
                    data = client.post_multipart("products/", body, files)
            else:
                data = client.post("products/", body)
    except RetailOpsError as e:
        handle_error(e)
        return
    except httpx.ConnectError as e:
        handle_connection_error(e, get_profile(state.profile).base_url)
        return
    print_success(f"Product '{data['name']}' created (id={data['id']}, sku={data['sku']}).")
    render(data, fmt)


# ── update ────────────────────────────────────────────────────────────────────

@app.command()
def update(
    id:              int            = typer.Argument(..., help="Product ID."),
    name:            Optional[str]  = typer.Option(None, "--name",         "-n"),
    sku:             Optional[str]  = typer.Option(None, "--sku",          "-S"),
    category_id:     Optional[int]  = typer.Option(None, "--category-id",  "-c"),
    unit_of_measure: Optional[str]  = typer.Option(None, "--unit",         "-u"),
    unit_price:      Optional[str]  = typer.Option(None, "--price",        "-p"),
    description:     Optional[str]  = typer.Option(None, "--description",  "-d"),
    threshold:       Optional[int]  = typer.Option(None, "--low-stock"),
    image:           Optional[str]  = typer.Option(None, "--image", help="Path to a replacement product image."),
    external_image_url: Optional[str] = typer.Option(None, "--external-image-url", help="External product image URL."),
    clear_image:     bool           = typer.Option(False, "--clear-image", help="Remove the uploaded product image."),
    clear_external_image_url: bool  = typer.Option(False, "--clear-external-image-url", help="Clear the external image URL."),
    is_active:       Optional[bool] = typer.Option(None, "--active/--inactive"),
    output:          Optional[str]  = typer.Option(None, "--output",      "-o"),
) -> None:
    """Update product fields. Requires Manager role. Only supplied fields are changed."""
    body: dict = {}
    for key, val in [
        ("name", name), ("sku", sku), ("category_id", category_id),
        ("unit_of_measure", unit_of_measure), ("unit_price", unit_price),
        ("description", description), ("low_stock_threshold", threshold),
        ("external_image_url", "" if clear_external_image_url else external_image_url),
        ("clear_image", True if clear_image else None),
        ("is_active", is_active),
    ]:
        if val is not None:
            body[key] = val
    if not body and not image:
        console.print("[yellow]No fields supplied. Nothing to update.[/yellow]")
        raise typer.Exit(0)
    fmt = output or state.output
    try:
        with _client() as client:
            if image:
                with multipart_file("image", image, label="product image") as files:
                    data = client.patch_multipart(f"products/{id}/", body, files)
            else:
                data = client.patch(f"products/{id}/", body)
    except RetailOpsError as e:
        handle_error(e)
        return
    except httpx.ConnectError as e:
        handle_connection_error(e, get_profile(state.profile).base_url)
        return
    print_success(f"Product {id} updated.")
    render(data, fmt)


# ── delete ────────────────────────────────────────────────────────────────────

@app.command()
def delete(
    id: int = typer.Argument(..., help="Product ID."),
) -> None:
    """Delete a product. Requires Manager role."""
    if not state.yes:
        if not typer.confirm(f"Delete product {id}?", default=False):
            abort()
    try:
        with _client() as client:
            client.delete(f"products/{id}/")
    except RetailOpsError as e:
        handle_error(e)
        return
    except httpx.ConnectError as e:
        handle_connection_error(e, get_profile(state.profile).base_url)
        return
    print_success(f"Product {id} deleted.")


# ── movements ────────────────────────────────────────────────────────────────

@app.command()
def movements(
    id:     int           = typer.Argument(..., help="Product ID."),
    page:   int           = typer.Option(1,    "--page", "-p"),
    all_:   bool          = typer.Option(False,"--all",  is_flag=True),
    output: Optional[str] = typer.Option(None, "--output", "-o"),
) -> None:
    """Show inventory movement history for a product (newest first)."""
    fmt = output or state.output
    try:
        with _client() as client:
            data = fetch_all(client, f"products/{id}/movements/") if all_ \
                   else paginated_get(client, f"products/{id}/movements/", page=page, page_size=state.page_size)
    except RetailOpsError as e:
        handle_error(e)
        return
    except httpx.ConnectError as e:
        handle_connection_error(e, get_profile(state.profile).base_url)
        return
    render(data, fmt, columns=[
        "id", "movement_type", "quantity", "reference_type",
        "reference_id", "created_by", "created_at",
    ])
