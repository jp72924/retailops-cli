"""
tests/test_inventory.py
-----------------------
Functional tests for stock adjustments through the CLI runner.

``inventory bulk-adjust`` is the second caller of render_partial_success (the
first is ``orders bulk-*``), and the partial-failure exit code has to hold for
both. The API answers 200 regardless of how many entries failed.
"""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from retailops_cli.__main__ import app


BASE = "http://test.example/api/v1"
TOKEN = "test-token-abc123"

runner = CliRunner()


@pytest.fixture
def cli_env(monkeypatch):
    """Point the CLI at the mock server via env-var overrides."""
    monkeypatch.setenv("RETAILOPS_BASE_URL", BASE)
    monkeypatch.setenv("RETAILOPS_TOKEN", TOKEN)
    yield


# ── adjust ────────────────────────────────────────────────────────────────────


def test_adjust_posts_signed_quantity(cli_env, httpx_mock, tmp_config):
    httpx_mock.add_response(
        url=f"{BASE}/inventory/adjust/", method="POST", status_code=201,
        json={"id": 12, "product": {"id": 5, "sku": "A1"}, "quantity": -3},
    )
    r = runner.invoke(app, [
        "--yes", "inventory", "adjust",
        "--product-id", "5", "--quantity", "-3", "--notes", "Damaged",
    ])
    assert r.exit_code == 0, r.stdout
    body = json.loads(httpx_mock.get_request().content)
    assert body == {"product_id": 5, "quantity": -3, "notes": "Damaged"}


def test_adjust_rejects_zero_quantity_before_sending(cli_env, httpx_mock, tmp_config):
    """Client-side guard: a zero adjustment is meaningless, so never send it."""
    r = runner.invoke(app, [
        "--yes", "inventory", "adjust", "--product-id", "5", "--quantity", "0",
    ])
    assert r.exit_code == 1
    assert httpx_mock.get_requests() == []


# ── bulk-adjust partial-success ───────────────────────────────────────────────


def test_bulk_adjust_partial_failure_exits_nonzero(cli_env, httpx_mock, tmp_config):
    httpx_mock.add_response(
        url=f"{BASE}/inventory/bulk-adjust/", method="POST",
        json={
            "succeeded": [{"id": 1, "quantity": 50}],
            "failed":    [{"product_id": 7, "error": "Product not found."}],
        },
    )
    r = runner.invoke(app, [
        "--output", "json", "inventory", "bulk-adjust",
        "--adjustments", '[{"product_id": 3, "quantity": 50}, {"product_id": 7, "quantity": -5}]',
    ])
    assert r.exit_code == 1, r.stdout
    assert "failed" in r.stdout


def test_bulk_adjust_total_failure_also_exits_one(cli_env, httpx_mock, tmp_config):
    """
    Every entry failing is still exit 1, not a distinct code — a script doing
    `cmd || handle` must catch this, and a separate code invites branching that
    misses the total-failure case.
    """
    httpx_mock.add_response(
        url=f"{BASE}/inventory/bulk-adjust/", method="POST",
        json={
            "succeeded": [],
            "failed":    [{"product_id": 7, "error": "Product not found."}],
        },
    )
    r = runner.invoke(app, [
        "inventory", "bulk-adjust", "--adjustments", '[{"product_id": 7, "quantity": -5}]',
    ])
    assert r.exit_code == 1, r.stdout


def test_bulk_adjust_clean_batch_exits_zero(cli_env, httpx_mock, tmp_config):
    httpx_mock.add_response(
        url=f"{BASE}/inventory/bulk-adjust/", method="POST",
        json={"succeeded": [{"id": 1, "quantity": 50}], "failed": []},
    )
    r = runner.invoke(app, [
        "inventory", "bulk-adjust", "--adjustments", '[{"product_id": 3, "quantity": 50}]',
    ])
    assert r.exit_code == 0, r.stdout


def test_bulk_adjust_rejects_zero_quantity_before_sending(cli_env, httpx_mock, tmp_config):
    r = runner.invoke(app, [
        "inventory", "bulk-adjust", "--adjustments", '[{"product_id": 3, "quantity": 0}]',
    ])
    assert r.exit_code == 1
    assert httpx_mock.get_requests() == []
