"""
retailops_cli.__main__
----------------------
Root Typer application. Registers all command groups and the global
option callback. Running `python -m retailops_cli` works in addition
to the `retailops-cli` console-script entry point.
"""

from __future__ import annotations

import typer

from . import __version__, state
from .config import get_setting
from .commands import (
    auth,
    categories,
    customers,
    inventory,
    kiosk,
    orders,
    payments,
    products,
    recipient_profiles,
    roles,
    schema,
    settings,
    users,
)
from .commands.dashboard import dashboard_command
from .commands.mcp_skill import mcp_skill_command

app = typer.Typer(
    name="retailops-cli",
    help="RetailOps command-line interface.",
    no_args_is_help=True,
    rich_markup_mode="rich",
    pretty_exceptions_show_locals=False,
)

# ── subcommand groups ─────────────────────────────────────────────────────────
app.add_typer(auth.app,               name="auth",               help="Authentication and profile management.")
app.add_typer(roles.app,              name="roles",              help="List system roles (Admin only).")
app.add_typer(users.app,              name="users",              help="Manage system users (Admin only).")
app.add_typer(customers.app,          name="customers",          help="Manage customers.")
app.add_typer(categories.app,         name="categories",         help="Manage product categories.")
app.add_typer(products.app,           name="products",           help="Manage products and stock.")
app.add_typer(inventory.app,          name="inventory",          help="View inventory movements and record adjustments.")
app.add_typer(orders.app,             name="orders",             help="Manage sales orders and lifecycle transitions.")
app.add_typer(payments.app,           name="payments",           help="Record and view payments.")
app.add_typer(recipient_profiles.app, name="recipient-profiles", help="Manage the payment recipient allowlist (Manager+).")
app.add_typer(settings.app,           name="settings",           help="View and update system settings.")
app.add_typer(kiosk.app,              name="kiosk",              help="Call kiosk API endpoints with a KioskKey.")
app.add_typer(schema.app,             name="schema",             help="Download OpenAPI schema and docs URLs.")

# ── single-command shortcuts ──────────────────────────────────────────────────
app.command(name="dashboard")(dashboard_command)
app.command(name="mcp-skill")(mcp_skill_command)


def _version_callback(value: bool) -> None:
    """Print the version and exit, before any other option is processed."""
    if value:
        typer.echo(f"retailops-cli {__version__}")
        raise typer.Exit(0)


@app.callback()
def _root(
    profile: str | None = typer.Option(
        None, "--profile", envvar="RETAILOPS_PROFILE",
        help="Config profile to use. Overrides the active profile in config.",
    ),
    output: str | None = typer.Option(
        None, "--output", "-o",
        help="Output format: [bold]table[/bold] (default) | [bold]json[/bold] | [bold]csv[/bold] | [bold]yaml[/bold].",
    ),
    yes: bool = typer.Option(
        False, "--yes", "-y",
        help="Skip all confirmation prompts (useful in scripts).",
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v",
        help="Print HTTP request/response details to stderr.",
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run",
        help="Preview mutating commands as method/URL/body and exit without calling the API.",
    ),
    page_size: int | None = typer.Option(
        None, "--page-size",
        help="Page size for list commands (max 100). Default 25; --all uses 100.",
    ),
    version: bool = typer.Option(
        False, "--version", "-V",
        callback=_version_callback, is_eager=True,
        help="Show the installed version and exit.",
    ),
) -> None:
    """RetailOps command-line interface."""
    # --output and --page-size default to None so a flag the user actually
    # typed can be told apart from the built-in default. That distinction
    # feeds two things: the [settings] table in config.toml, whose
    # output_format / page_size keys were documented but never read; and
    # --all, which keeps requesting 100 per page unless asked otherwise.
    state.profile   = profile
    state.output    = output or get_setting("output_format", "table")
    state.yes       = yes
    state.verbose   = verbose
    state.dry_run   = dry_run
    state.page_size_explicit = page_size is not None
    if page_size is None:
        page_size = get_setting("page_size", 25)
        state.page_size_explicit = page_size != 25
    state.page_size = min(int(page_size), 100)


if __name__ == "__main__":
    app()
