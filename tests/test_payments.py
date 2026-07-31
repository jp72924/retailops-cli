"""
tests/test_payments.py
----------------------
Functional tests for `payments record`, focused on the client-side --ref guard.

The server requires a reference number for bank_transfer, card, and check
payments. The CLI mirrors that rule so the failure arrives immediately instead
of after a round-trip — which means these tests care as much about no request
being issued as about the exit code.
"""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from retailops_cli.__main__ import app


BASE = "http://test.example/api/v1"
TOKEN = "test-token-abc123"

runner = CliRunner()

REFERENCE_REQUIRED = ["bank_transfer", "card", "check"]
REFERENCE_OPTIONAL = ["cash", "mobile_payment", "other"]


@pytest.fixture
def cli_env(monkeypatch):
    """Point the CLI at the mock server via env-var overrides."""
    monkeypatch.setenv("RETAILOPS_BASE_URL", BASE)
    monkeypatch.setenv("RETAILOPS_TOKEN", TOKEN)
    yield


def _record(*extra):
    return runner.invoke(app, [
        "payments", "record", "--order", "88", "--amount", "10.00", *extra,
    ])


# ── the --ref guard ───────────────────────────────────────────────────────────


@pytest.mark.parametrize("method", REFERENCE_REQUIRED)
def test_reference_required_methods_fail_before_any_request(
    cli_env, httpx_mock, tmp_config, method,
):
    r = _record("--method", method)

    assert r.exit_code == 1
    assert "--ref is required" in r.stderr
    assert method in r.stderr
    # The whole point of the guard: no round-trip to discover this.
    assert httpx_mock.get_requests() == []


@pytest.mark.parametrize("method", REFERENCE_REQUIRED)
def test_whitespace_reference_is_rejected_like_a_missing_one(
    cli_env, httpx_mock, tmp_config, method,
):
    """The server trims before checking, so "   " is blank there too."""
    r = _record("--method", method, "--ref", "   ")

    assert r.exit_code == 1
    assert httpx_mock.get_requests() == []


@pytest.mark.parametrize("method", REFERENCE_REQUIRED)
def test_reference_required_methods_send_when_ref_supplied(
    cli_env, httpx_mock, tmp_config, method,
):
    httpx_mock.add_response(
        url=f"{BASE}/payments/", method="POST", status_code=201,
        json={
            "id": 1, "payment_number": "PAY-1", "amount": "10.00",
            "payment_method": method, "reference_number": "REF-1",
        },
    )
    r = _record("--method", method, "--ref", "REF-1")

    assert r.exit_code == 0, r.stdout
    body = json.loads(httpx_mock.get_request().content)
    assert body["payment_method"] == method
    assert body["reference_number"] == "REF-1"


@pytest.mark.parametrize("method", REFERENCE_OPTIONAL)
def test_other_methods_do_not_require_a_reference(
    cli_env, httpx_mock, tmp_config, method,
):
    """Guard against over-broadening the rule beyond the server's three."""
    httpx_mock.add_response(
        url=f"{BASE}/payments/", method="POST", status_code=201,
        json={
            "id": 1, "payment_number": "PAY-1", "amount": "10.00",
            "payment_method": method,
        },
    )
    r = _record("--method", method)

    assert r.exit_code == 0, r.stdout
    assert len(httpx_mock.get_requests()) == 1


# ── the pre-existing method whitelist still runs first ────────────────────────


def test_unknown_method_is_rejected_before_the_reference_check(
    cli_env, httpx_mock, tmp_config,
):
    """
    Ordering matters: the reference guard assumes the method is already valid,
    so an unknown one must report as an invalid method, not a missing --ref.
    """
    r = _record("--method", "wire")

    assert r.exit_code == 1
    assert "Invalid payment method" in r.stderr
    assert "--ref is required" not in r.stderr
    assert httpx_mock.get_requests() == []
