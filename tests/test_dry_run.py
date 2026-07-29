"""
tests/test_dry_run.py
---------------------
Verifies that ``--dry-run`` short-circuits *every* mutating command: NO HTTP
request leaves the process, exit code is 0, and the DRY-RUN preview reaches
stdout.

--dry-run is enforced centrally in ``client._send``, so coverage here is about
proving the gate catches every verb and every command path — including the ones
that were silently ignoring the flag before (deletes, lifecycle transitions,
bulk operations, creates and updates).

The single ``no_http_calls`` fixture queues zero responses and relies on
pytest-httpx's strict default to fail loud if any HTTP call slips through.
"""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from retailops_cli.__main__ import app


runner = CliRunner()


@pytest.fixture
def cli_env(monkeypatch):
    """Configure CLI to point at a URL that should never be reached under --dry-run."""
    monkeypatch.setenv("RETAILOPS_BASE_URL", "http://test.example/api/v1")
    monkeypatch.setenv("RETAILOPS_TOKEN", "dummy-token")
    yield


@pytest.fixture
def no_http_calls(httpx_mock):
    """Queue no responses. If any command actually calls HTTP, pytest-httpx fails."""
    yield httpx_mock
    # If a request slipped through, get_requests() would have entries.
    assert len(httpx_mock.get_requests()) == 0, (
        f"--dry-run leaked HTTP calls: {[r.method + ' ' + str(r.url) for r in httpx_mock.get_requests()]}"
    )


# ── parametrised dry-run shortcut ─────────────────────────────────────────────


@pytest.mark.parametrize("argv,expected_method,expected_path", [
    (["--dry-run", "--yes", "orders", "refund", "42"],
     "POST", "orders/42/refund/"),
    (["--dry-run", "--yes", "orders", "cancel", "42"],
     "POST", "orders/42/cancel/"),
    (["--dry-run", "--yes", "customers", "delete", "9"],
     "DELETE", "customers/9/"),
    (["--dry-run", "--yes", "users", "deactivate", "3"],
     "POST", "users/3/deactivate/"),
])
def test_dry_run_skips_http_for_simple_commands(
    cli_env, no_http_calls, tmp_config, argv, expected_method, expected_path,
):
    r = runner.invoke(app, argv)
    assert r.exit_code == 0, r.stdout
    assert "DRY RUN" in r.stdout
    assert expected_method in r.stdout
    assert expected_path in r.stdout


# ── commands that used to ignore --dry-run entirely ───────────────────────────


@pytest.mark.parametrize("argv,expected_method,expected_path", [
    # Destructive deletes — these previously deleted the record outright.
    (["--dry-run", "--yes", "orders", "delete", "5"],
     "DELETE", "orders/5/"),
    (["--dry-run", "--yes", "products", "delete", "8"],
     "DELETE", "products/8/"),
    (["--dry-run", "--yes", "categories", "delete", "2"],
     "DELETE", "categories/2/"),
    # Lifecycle transitions — `confirm` deducts stock.
    (["--dry-run", "orders", "submit", "7"],
     "POST", "orders/7/submit/"),
    (["--dry-run", "orders", "confirm", "7"],
     "POST", "orders/7/confirm/"),
    (["--dry-run", "orders", "ship", "7"],
     "POST", "orders/7/ship/"),
    (["--dry-run", "orders", "deliver", "7"],
     "POST", "orders/7/deliver/"),
    # Bulk transitions.
    (["--dry-run", "orders", "bulk-confirm", "--id", "1", "--id", "2"],
     "POST", "orders/bulk-transition/"),
    (["--dry-run", "orders", "bulk-ship", "--id", "3"],
     "POST", "orders/bulk-transition/"),
    (["--dry-run", "orders", "bulk-deliver", "--id", "4"],
     "POST", "orders/bulk-transition/"),
    # Creates and updates.
    (["--dry-run", "categories", "create", "--name", "Tools"],
     "POST", "categories/"),
    (["--dry-run", "categories", "update", "2", "--name", "Hardware"],
     "PATCH", "categories/2/"),
    (["--dry-run", "customers", "update", "4", "--city", "Lisbon"],
     "PATCH", "customers/4/"),
    (["--dry-run", "users", "reactivate", "3"],
     "POST", "users/3/reactivate/"),
    (["--dry-run", "settings", "update", "--currency-code", "EUR"],
     "PATCH", "settings/"),
])
def test_dry_run_covers_previously_unwired_commands(
    cli_env, no_http_calls, tmp_config, argv, expected_method, expected_path,
):
    """
    Regression guard for the parity audit's headline defect: these commands
    accepted --dry-run and sent the request anyway.
    """
    r = runner.invoke(app, argv)
    assert r.exit_code == 0, r.stdout
    assert "DRY RUN" in r.stdout
    assert expected_method in r.stdout
    assert expected_path in r.stdout


def test_dry_run_does_not_prompt_without_yes(cli_env, no_http_calls, tmp_config):
    """
    --dry-run must skip the confirmation prompt, not just the request.

    Under CliRunner, stdin is at EOF; if the prompt still fired, click would
    raise Abort and the command would exit 1 instead of 0.
    """
    r = runner.invoke(app, ["--dry-run", "orders", "delete", "5"])
    assert r.exit_code == 0, r.stdout
    assert "DRY RUN" in r.stdout
    assert "Delete order 5?" not in r.stdout


def test_dry_run_redacts_secrets_in_preview(cli_env, no_http_calls, tmp_config):
    """A preview must never echo a credential back to the terminal."""
    r = runner.invoke(app, [
        "--dry-run", "users", "create",
        "--email", "a@b.co", "--first-name", "A", "--last-name", "B",
        "--role", "2", "--password", "sup3rs3cret",
    ])
    assert r.exit_code == 0, r.stdout
    assert "DRY RUN" in r.stdout
    assert "sup3rs3cret" not in r.stdout
    assert "***" in r.stdout


def test_dry_run_does_not_block_read_commands(cli_env, httpx_mock, tmp_config):
    """GET is exempt: --dry-run previews mutations, it does not disable reads."""
    httpx_mock.add_response(
        url="http://test.example/api/v1/orders/42/",
        method="GET",
        json={"id": 42, "order_number": "SO-1", "status": "draft"},
    )
    r = runner.invoke(app, ["--dry-run", "orders", "get", "42"])
    assert r.exit_code == 0, r.stdout
    assert len(httpx_mock.get_requests()) == 1
    assert "DRY RUN" not in r.stdout


def test_dry_run_inventory_adjust_includes_body(cli_env, no_http_calls, tmp_config):
    r = runner.invoke(app, [
        "--dry-run", "--yes",
        "inventory", "adjust",
        "--product-id", "5", "--quantity", "-3", "--notes", "Damaged",
    ])
    assert r.exit_code == 0, r.stdout
    assert "DRY RUN" in r.stdout
    assert "POST" in r.stdout
    assert "inventory/adjust/" in r.stdout
    # Body should surface the field values.
    assert "product_id" in r.stdout
    assert "5" in r.stdout
    assert "-3" in r.stdout
    assert "Damaged" in r.stdout


def test_dry_run_inventory_bulk_adjust_includes_body(cli_env, no_http_calls, tmp_config):
    r = runner.invoke(app, [
        "--dry-run",
        "inventory", "bulk-adjust",
        "--adjustments", '[{"product_id": 3, "quantity": 50}]',
    ])
    assert r.exit_code == 0, r.stdout
    assert "DRY RUN" in r.stdout
    assert "inventory/bulk-adjust/" in r.stdout
    assert "adjustments" in r.stdout


# ── without --dry-run, HTTP IS attempted (sanity check) ───────────────────────


def test_without_dry_run_http_call_is_attempted(cli_env, httpx_mock, tmp_config):
    """Sanity check: removing --dry-run results in an actual HTTP call."""
    httpx_mock.add_response(
        url="http://test.example/api/v1/orders/42/refund/",
        method="POST",
        json={"id": 42, "status": "refunded"},
    )
    r = runner.invoke(app, ["--yes", "orders", "refund", "42"])
    assert r.exit_code == 0, r.stdout
    # If --dry-run had still been active, no request would have been made.
    assert len(httpx_mock.get_requests()) == 1
    assert httpx_mock.get_request().url.path == "/api/v1/orders/42/refund/"
