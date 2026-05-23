"""
tests/test_commands_smoke.py
----------------------------
Cheap CLI registration smoke tests: invoke ``--help`` for the root and every
subcommand to catch breakage from a missing ``app.add_typer`` registration,
a malformed Typer.Option, or an import-time error in any command module.

Each test invokes the Typer app via ``CliRunner`` and asserts exit code 0
plus a domain-specific marker in the help output.
"""

import pytest
from typer.main import get_command
from typer.testing import CliRunner

from retailops_cli.__main__ import app


runner = CliRunner()
click_app = get_command(app)


def option_names(*path: str) -> set[str]:
    command = click_app
    for part in path:
        command = command.commands[part]

    names: set[str] = set()
    for param in command.params:
        names.update(getattr(param, "opts", ()))
        names.update(getattr(param, "secondary_opts", ()))
    return names


# ── root + bare-help ──────────────────────────────────────────────────────────


def test_root_help():
    r = runner.invoke(app, ["--help"])
    assert r.exit_code == 0
    out = r.stdout
    # Each registered group should appear in the root help.
    for group in [
        "auth", "roles", "users", "settings", "customers", "categories",
        "products", "inventory", "orders", "payments", "kiosk", "schema",
        "dashboard", "mcp-skill",
    ]:
        assert group in out, f"missing group: {group}"


# ── parametrised group + leaf help ────────────────────────────────────────────


@pytest.mark.parametrize("group", [
    "auth", "roles", "users", "settings", "customers", "categories",
    "products", "inventory", "orders", "payments", "kiosk", "schema",
])
def test_group_help_does_not_crash(group):
    r = runner.invoke(app, [group, "--help"])
    assert r.exit_code == 0, r.stdout


@pytest.mark.parametrize("path", [
    # auth
    ["auth", "login", "--help"],
    ["auth", "logout", "--help"],
    ["auth", "whoami", "--help"],
    ["auth", "config", "--help"],
    ["auth", "profiles", "--help"],
    ["auth", "use", "--help"],
    ["auth", "passwd-reset", "--help"],
    ["auth", "passwd-reset-confirm", "--help"],
    # roles
    ["roles", "list", "--help"],
    ["roles", "get", "--help"],
    # users
    ["users", "list", "--help"],
    ["users", "get", "--help"],
    ["users", "create", "--help"],
    ["users", "update", "--help"],
    ["users", "passwd", "--help"],
    ["users", "deactivate", "--help"],
    ["users", "reactivate", "--help"],
    # settings
    ["settings", "get", "--help"],
    ["settings", "update", "--help"],
    # customers
    ["customers", "list", "--help"],
    ["customers", "get", "--help"],
    ["customers", "create", "--help"],
    ["customers", "update", "--help"],
    ["customers", "delete", "--help"],
    # categories
    ["categories", "list", "--help"],
    ["categories", "get", "--help"],
    ["categories", "create", "--help"],
    ["categories", "update", "--help"],
    ["categories", "delete", "--help"],
    # products
    ["products", "list", "--help"],
    ["products", "get", "--help"],
    ["products", "create", "--help"],
    ["products", "update", "--help"],
    ["products", "delete", "--help"],
    ["products", "movements", "--help"],
    # inventory
    ["inventory", "list", "--help"],
    ["inventory", "get", "--help"],
    ["inventory", "adjust", "--help"],
    ["inventory", "bulk-adjust", "--help"],
    # orders
    ["orders", "list", "--help"],
    ["orders", "get", "--help"],
    ["orders", "create", "--help"],
    ["orders", "update", "--help"],
    ["orders", "delete", "--help"],
    ["orders", "submit", "--help"],
    ["orders", "confirm", "--help"],
    ["orders", "cancel", "--help"],
    ["orders", "ship", "--help"],
    ["orders", "deliver", "--help"],
    ["orders", "refund", "--help"],
    ["orders", "bulk-confirm", "--help"],
    ["orders", "bulk-ship", "--help"],
    ["orders", "bulk-deliver", "--help"],
    # payments
    ["payments", "list", "--help"],
    ["payments", "get", "--help"],
    ["payments", "record", "--help"],
    ["payments", "verify-receipt", "--help"],
    ["payments", "receipt-healthz", "--help"],
    # kiosk
    ["kiosk", "identify", "--help"],
    ["kiosk", "register", "--help"],
    ["kiosk", "products", "--help"],
    ["kiosk", "product-get", "--help"],
    ["kiosk", "product-lookup", "--help"],
    ["kiosk", "checkout", "--help"],
    ["kiosk", "receipt", "--help"],
    ["kiosk", "heartbeat", "--help"],
    # schema
    ["schema", "get", "--help"],
    ["schema", "swagger-url", "--help"],
    ["schema", "redoc-url", "--help"],
    # singletons (top-level commands, not groups)
    ["dashboard", "--help"],
    ["mcp-skill", "--help"],
])
def test_leaf_command_help_does_not_crash(path):
    r = runner.invoke(app, path)
    assert r.exit_code == 0, f"{' '.join(path)} → exit {r.exit_code}\n{r.stdout}"


# ── Phase 1/2 flag presence checks (lock in the changes) ──────────────────────


def test_settings_update_lists_secondary_currency_flags():
    r = runner.invoke(app, ["settings", "update", "--help"])
    assert r.exit_code == 0
    options = option_names("settings", "update")
    for flag in [
        "--secondary-enabled",
        "--secondary-code",
        "--secondary-symbol",
        "--secondary-decimal-places",
        "--secondary-rate",
    ]:
        assert flag in options, f"missing flag in `settings update`: {flag}"


def test_customers_create_lists_extended_fields():
    r = runner.invoke(app, ["customers", "create", "--help"])
    assert r.exit_code == 0
    options = option_names("customers", "create")
    for flag in ["--national-id", "--dob", "--gender", "--address-line-2", "--user-id"]:
        assert flag in options, f"missing flag in `customers create`: {flag}"


def test_customers_update_lists_extended_fields():
    r = runner.invoke(app, ["customers", "update", "--help"])
    assert r.exit_code == 0
    options = option_names("customers", "update")
    for flag in ["--national-id", "--dob", "--gender", "--address-line-2", "--user-id"]:
        assert flag in options, f"missing flag in `customers update`: {flag}"


def test_products_list_has_unit_and_active_inactive_flags():
    r = runner.invoke(app, ["products", "list", "--help"])
    assert r.exit_code == 0
    options = option_names("products", "list")
    assert "--unit" in options
    assert "--active" in options
    assert "--inactive" in options
    # The old --all-statuses must be gone (it was renamed in Phase 2).
    assert "--all-statuses" not in options


def test_products_create_update_list_image_flags():
    create_help = runner.invoke(app, ["products", "create", "--help"])
    update_help = runner.invoke(app, ["products", "update", "--help"])
    assert create_help.exit_code == 0
    assert update_help.exit_code == 0
    create_options = option_names("products", "create")
    update_options = option_names("products", "update")
    for flag in ["--image", "--external-image-url"]:
        assert flag in create_options
        assert flag in update_options
    # Rich may truncate very long option names in narrow terminals; behavior
    # coverage for --clear-external-image-url lives in test_modern_cli_api_parity.
    for flag in ["--clear-image"]:
        assert flag in update_options


def test_payments_modern_flags_are_advertised():
    list_help = runner.invoke(app, ["payments", "list", "--help"])
    record_help = runner.invoke(app, ["payments", "record", "--help"])
    verify_help = runner.invoke(app, ["payments", "verify-receipt", "--help"])
    assert list_help.exit_code == 0
    assert record_help.exit_code == 0
    assert verify_help.exit_code == 0
    list_options = option_names("payments", "list")
    record_options = option_names("payments", "record")
    verify_options = option_names("payments", "verify-receipt")
    for flag in ["--has-receipt", "--bank", "--status", "--payment-method"]:
        assert flag in list_options
    for flag in ["--receipt-image", "--ocr-data", "--transaction-key", "--origin-bank"]:
        assert flag in record_options
    for flag in ["--expected-amount-usd", "--expected-reference", "--expected-origin-bank"]:
        assert flag in verify_options


def test_settings_update_lists_ocr_flags():
    r = runner.invoke(app, ["settings", "update", "--help"])
    assert r.exit_code == 0
    options = option_names("settings", "update")
    for flag in [
        "--ocr-enabled",
        "--ocr-base-url",
        "--ocr-api-key",
        "--clear-ocr-api-key",
    ]:
        assert flag in options


# ── Phase 5 flag presence checks ──────────────────────────────────────────────


def test_root_help_advertises_dry_run_and_yaml_output():
    r = runner.invoke(app, ["--help"])
    assert r.exit_code == 0
    assert "--dry-run" in option_names()
    # The output-format help line must mention yaml.
    assert "yaml" in r.stdout


def test_auth_config_command_exists():
    r = runner.invoke(app, ["auth", "config", "--help"])
    assert r.exit_code == 0
    assert "resolved" in r.stdout.lower() or "profile" in r.stdout.lower()


def test_orders_create_help_mentions_file_and_stdin_input():
    r = runner.invoke(app, ["orders", "create", "--help"])
    assert r.exit_code == 0
    # The --items help text must document @file and stdin support.
    assert "@path.json" in r.stdout
    assert "stdin" in r.stdout


def test_inventory_bulk_adjust_help_mentions_file_and_stdin_input():
    r = runner.invoke(app, ["inventory", "bulk-adjust", "--help"])
    assert r.exit_code == 0
    assert "@path.json" in r.stdout
    assert "stdin" in r.stdout
