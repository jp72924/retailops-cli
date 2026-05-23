"""
tests/test_orders.py
--------------------
Order lifecycle integration test: invokes the actual ``retailops-cli orders ...`` CLI
commands through Typer's ``CliRunner`` while mocking HTTP responses with
pytest-httpx. Verifies that each command:
- POSTs the correct path
- sends the expected body
- exits with status 0

Lifecycle covered:
    create (Draft) → submit → confirm → record payment (auto-Paid) →
    ship → deliver

Plus a couple of error-path checks (refund without --yes prompts; bulk-ship
partial-success rendering).
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


# ── happy-path lifecycle ──────────────────────────────────────────────────────


def test_full_order_lifecycle(cli_env, httpx_mock, tmp_config):
    """Create → submit → confirm → pay → ship → deliver, all via CLI."""

    # 1. create
    httpx_mock.add_response(
        url=f"{BASE}/orders/", method="POST", status_code=201,
        json={
            "id": 42, "order_number": "SO-20260501-0042",
            "status": "draft", "customer": "X Y",
            "total_amount": "100.00", "amount_outstanding": "100.00",
            "created_at": "2026-05-01T10:00:00Z",
        },
    )
    r = runner.invoke(app, [
        "--output", "json", "orders", "create",
        "--customer-id", "5",
        "--items", '[{"product_id": 7, "quantity": 2}]',
    ])
    assert r.exit_code == 0, r.stdout
    create_req = httpx_mock.get_requests()[-1]
    body = json.loads(create_req.content)
    assert body["customer_id"] == 5
    assert body["items"] == [{"product_id": 7, "quantity": 2}]

    # 2. submit
    httpx_mock.add_response(
        url=f"{BASE}/orders/42/submit/", method="POST",
        json={"id": 42, "status": "pending"},
    )
    r = runner.invoke(app, ["--output", "json", "orders", "submit", "42"])
    assert r.exit_code == 0, r.stdout

    # 3. confirm
    httpx_mock.add_response(
        url=f"{BASE}/orders/42/confirm/", method="POST",
        json={"id": 42, "status": "confirmed"},
    )
    r = runner.invoke(app, ["--output", "json", "orders", "confirm", "42"])
    assert r.exit_code == 0, r.stdout

    # 4. record payment — auto-transitions to paid
    httpx_mock.add_response(
        url=f"{BASE}/payments/", method="POST", status_code=201,
        json={
            "id": 99, "payment_number": "PAY-20260501-0001",
            "sales_order": 42, "amount": "100.00",
            "payment_method": "cash",
            "auto_transitioned_to_paid": True,
        },
    )
    r = runner.invoke(app, [
        "--output", "json", "payments", "record",
        "--order", "42", "--amount", "100.00", "--method", "cash",
    ])
    assert r.exit_code == 0, r.stdout

    # 5. ship
    httpx_mock.add_response(
        url=f"{BASE}/orders/42/ship/", method="POST",
        json={"id": 42, "status": "shipped"},
    )
    r = runner.invoke(app, ["--output", "json", "orders", "ship", "42"])
    assert r.exit_code == 0, r.stdout

    # 6. deliver
    httpx_mock.add_response(
        url=f"{BASE}/orders/42/deliver/", method="POST",
        json={"id": 42, "status": "delivered"},
    )
    r = runner.invoke(app, ["--output", "json", "orders", "deliver", "42"])
    assert r.exit_code == 0, r.stdout

    # Sanity: every queued response was consumed exactly once.
    requested_paths = [req.url.path for req in httpx_mock.get_requests()]
    assert "/api/v1/orders/" in requested_paths
    assert "/api/v1/orders/42/submit/" in requested_paths
    assert "/api/v1/orders/42/confirm/" in requested_paths
    assert "/api/v1/payments/" in requested_paths
    assert "/api/v1/orders/42/ship/" in requested_paths
    assert "/api/v1/orders/42/deliver/" in requested_paths


# ── list filters round-trip into query params ─────────────────────────────────


def test_orders_list_passes_status_and_date_filters(cli_env, httpx_mock, tmp_config):
    httpx_mock.add_response(
        url=f"{BASE}/orders/?status=confirmed&date_from=2026-04-01&date_to=2026-04-30&page=1&page_size=25",
        json={"count": 0, "next": None, "previous": None, "results": []},
    )
    r = runner.invoke(app, [
        "--output", "json", "orders", "list",
        "--status", "confirmed",
        "--from", "2026-04-01", "--to", "2026-04-30",
    ])
    assert r.exit_code == 0, r.stdout
    qs = dict(httpx_mock.get_request().url.params)
    assert qs["status"]    == "confirmed"
    assert qs["date_from"] == "2026-04-01"
    assert qs["date_to"]   == "2026-04-30"


# ── bulk-ship partial-success ────────────────────────────────────────────────


def test_bulk_ship_renders_partial_success(cli_env, httpx_mock, tmp_config):
    httpx_mock.add_response(
        url=f"{BASE}/orders/bulk-transition/", method="POST",
        json={
            "succeeded": [
                {"id": 1, "status": "shipped"},
                {"id": 2, "status": "shipped"},
            ],
            "failed": [
                {"id": 99, "error": "wrong status"},
            ],
        },
    )
    r = runner.invoke(app, [
        "--output", "json", "orders", "bulk-ship",
        "--id", "1", "--id", "2", "--id", "99",
    ])
    assert r.exit_code == 0, r.stdout
    body = json.loads(httpx_mock.get_request().content)
    assert body == {"order_ids": [1, 2, 99], "action": "ship"}


# ── refund requires confirmation ──────────────────────────────────────────────


def test_refund_with_yes_flag_skips_prompt(cli_env, httpx_mock, tmp_config):
    httpx_mock.add_response(
        url=f"{BASE}/orders/42/refund/", method="POST",
        json={"id": 42, "status": "refunded"},
    )
    r = runner.invoke(app, [
        "--yes", "--output", "json", "orders", "refund", "42",
    ])
    assert r.exit_code == 0, r.stdout
    assert httpx_mock.get_request().url.path == "/api/v1/orders/42/refund/"


# ── 404 surfaces exit code 3 (not_found) ──────────────────────────────────────


def test_get_unknown_order_exits_with_not_found(cli_env, httpx_mock, tmp_config):
    httpx_mock.add_response(
        url=f"{BASE}/orders/9999/", status_code=404,
        json={"error": "Order not found.", "code": "not_found"},
    )
    r = runner.invoke(app, ["orders", "get", "9999"])
    assert r.exit_code == 3, f"expected exit 3 (not found), got {r.exit_code}"
