"""
tests/test_dry_run.py
---------------------
Verifies that ``--dry-run`` short-circuits each of the six wired mutating
commands: NO HTTP request leaves the process, exit code is 0, and the
DRY-RUN preview reaches stdout.

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
