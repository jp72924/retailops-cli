"""
tests/test_recipient_profiles.py
--------------------------------
Functional tests for the recipient-profile CRUD group and the settings
commands it unblocks.

This domain had zero CLI coverage before — the allowlist that OCR-verified
receipts are matched against could be neither read nor populated, and
--recipient-validation could not be switched on because the server rejects it
unless an active profile already exists.
"""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from retailops_cli.__main__ import app


BASE = "http://test.example/api/v1"
TOKEN = "test-token-abc123"
PATH = "payment-recipient-profiles"

runner = CliRunner()


@pytest.fixture
def cli_env(monkeypatch):
    """Point the CLI at the mock server via env-var overrides."""
    monkeypatch.setenv("RETAILOPS_BASE_URL", BASE)
    monkeypatch.setenv("RETAILOPS_TOKEN", TOKEN)
    yield


# ── list ──────────────────────────────────────────────────────────────────────


def test_list_passes_filters_and_pagination(cli_env, httpx_mock, tmp_config):
    httpx_mock.add_response(
        url=f"{BASE}/{PATH}/?is_active=true&ordering=label&page=1&page_size=25"
            "&payment_method=mobile_payment&search=BDV",
        json={"count": 0, "next": None, "previous": None, "results": []},
    )
    r = runner.invoke(app, [
        "recipient-profiles", "list",
        "--method", "mobile_payment", "--active",
        "--search", "BDV", "--ordering", "label",
    ])
    assert r.exit_code == 0, r.stdout
    qs = dict(httpx_mock.get_request().url.params)
    assert qs["payment_method"] == "mobile_payment"
    assert qs["is_active"] == "true"
    assert qs["search"] == "BDV"


def test_list_rejects_an_unknown_method_before_sending(cli_env, httpx_mock, tmp_config):
    r = runner.invoke(app, ["recipient-profiles", "list", "--method", "carrier_pigeon"])
    assert r.exit_code == 1
    assert "Invalid --method" in r.stderr
    assert httpx_mock.get_requests() == []


def test_list_all_walks_every_page(cli_env, httpx_mock, tmp_config):
    httpx_mock.add_response(
        url=f"{BASE}/{PATH}/?page=1&page_size=100",
        json={
            "count": 2, "next": f"{BASE}/{PATH}/?page=2&page_size=100",
            "previous": None, "results": [{"id": 1, "label": "A"}],
        },
    )
    httpx_mock.add_response(
        url=f"{BASE}/{PATH}/?page=2&page_size=100",
        json={"count": 2, "next": None, "previous": None, "results": [{"id": 2, "label": "B"}]},
    )
    r = runner.invoke(app, ["--output", "json", "recipient-profiles", "list", "--all"])
    assert r.exit_code == 0, r.stdout
    assert len(json.loads(r.stdout)["results"]) == 2


# ── create ────────────────────────────────────────────────────────────────────


def test_create_mobile_payment_profile(cli_env, httpx_mock, tmp_config):
    httpx_mock.add_response(
        url=f"{BASE}/{PATH}/", method="POST", status_code=201,
        json={"id": 3, "payment_method": "mobile_payment", "phone": "04121234567"},
    )
    r = runner.invoke(app, [
        "recipient-profiles", "create",
        "--method", "mobile_payment", "--phone", "04121234567",
        "--bank", "BDV", "--document-id", "V12345678", "--label", "Main line",
    ])
    assert r.exit_code == 0, r.stdout
    body = json.loads(httpx_mock.get_request().content)
    assert body == {
        "payment_method": "mobile_payment",
        "bank":           "BDV",
        "document_id":    "V12345678",
        "phone":          "04121234567",
        "label":          "Main line",
        "is_active":      True,
    }
    # account_number was never supplied, so it must not appear in the payload.
    assert "account_number" not in body


def test_create_bank_transfer_profile(cli_env, httpx_mock, tmp_config):
    httpx_mock.add_response(
        url=f"{BASE}/{PATH}/", method="POST", status_code=201,
        json={"id": 4, "payment_method": "bank_transfer"},
    )
    r = runner.invoke(app, [
        "recipient-profiles", "create",
        "--method", "bank_transfer", "--account-number", "01020304050607080910",
        "--bank", "Banesco", "--document-id", "V456", "--inactive",
    ])
    assert r.exit_code == 0, r.stdout
    body = json.loads(httpx_mock.get_request().content)
    assert body["account_number"] == "01020304050607080910"
    assert body["is_active"] is False


def test_create_surfaces_the_servers_pairing_rule(cli_env, httpx_mock, tmp_config):
    """
    The phone/account_number pairing is enforced server-side; the CLI should
    relay that field-level message rather than duplicating the rule.
    """
    httpx_mock.add_response(
        url=f"{BASE}/{PATH}/", method="POST", status_code=400,
        json={
            "error": "Invalid input.", "code": "validation_error",
            "details": {"phone": ["Required for mobile payment profiles."]},
        },
    )
    r = runner.invoke(app, [
        "recipient-profiles", "create",
        "--method", "mobile_payment", "--bank", "BDV", "--document-id", "V1",
    ])
    assert r.exit_code == 1
    assert "Required for mobile payment profiles." in r.stderr


# ── update / delete ───────────────────────────────────────────────────────────


def test_update_sends_only_supplied_fields(cli_env, httpx_mock, tmp_config):
    httpx_mock.add_response(
        url=f"{BASE}/{PATH}/3/", method="PATCH",
        json={"id": 3, "label": "Renamed"},
    )
    r = runner.invoke(app, ["recipient-profiles", "update", "3", "--label", "Renamed"])
    assert r.exit_code == 0, r.stdout
    assert json.loads(httpx_mock.get_request().content) == {"label": "Renamed"}


def test_update_with_no_flags_does_not_call_the_api(cli_env, httpx_mock, tmp_config):
    r = runner.invoke(app, ["recipient-profiles", "update", "3"])
    assert r.exit_code == 0
    assert "Nothing to update" in r.stdout
    assert httpx_mock.get_requests() == []


def test_deactivating_keeps_the_record(cli_env, httpx_mock, tmp_config):
    """--inactive is the non-destructive alternative to delete."""
    httpx_mock.add_response(
        url=f"{BASE}/{PATH}/3/", method="PATCH",
        json={"id": 3, "is_active": False},
    )
    r = runner.invoke(app, ["recipient-profiles", "update", "3", "--inactive"])
    assert r.exit_code == 0, r.stdout
    assert json.loads(httpx_mock.get_request().content) == {"is_active": False}


def test_delete_prompts_before_removing(cli_env, httpx_mock, tmp_config):
    r = runner.invoke(app, ["recipient-profiles", "delete", "3"], input="n\n")
    assert r.exit_code == 130
    assert httpx_mock.get_requests() == []


def test_delete_with_yes_skips_the_prompt(cli_env, httpx_mock, tmp_config):
    httpx_mock.add_response(url=f"{BASE}/{PATH}/3/", method="DELETE", status_code=204)
    r = runner.invoke(app, ["--yes", "recipient-profiles", "delete", "3"])
    assert r.exit_code == 0, r.stdout
    assert httpx_mock.get_request().method == "DELETE"


def test_delete_honors_dry_run(cli_env, httpx_mock, tmp_config):
    r = runner.invoke(app, ["--dry-run", "recipient-profiles", "delete", "3"])
    assert r.exit_code == 0, r.stdout
    assert "DRY RUN" in r.stdout
    assert httpx_mock.get_requests() == []


# ── the settings commands this domain unblocks ────────────────────────────────


def test_settings_update_can_enable_recipient_validation(cli_env, httpx_mock, tmp_config):
    """
    The flag existed on the server but had no CLI surface, so the whole
    recipient-validation feature was unreachable in both directions.
    """
    httpx_mock.add_response(
        url=f"{BASE}/settings/", method="PATCH",
        json={"recipient_validation_enabled": True},
    )
    r = runner.invoke(app, ["settings", "update", "--recipient-validation"])
    assert r.exit_code == 0, r.stdout
    assert json.loads(httpx_mock.get_request().content) == {"recipient_validation_enabled": True}


def test_settings_update_sends_the_rate_automation_trio(cli_env, httpx_mock, tmp_config):
    httpx_mock.add_response(url=f"{BASE}/settings/", method="PATCH", json={})
    r = runner.invoke(app, [
        "settings", "update",
        "--secondary-rate-auto",
        "--secondary-rate-source-url", "https://rates.test/oficial",
        "--secondary-rate-source-field", "promedio",
    ])
    assert r.exit_code == 0, r.stdout
    assert json.loads(httpx_mock.get_request().content) == {
        "secondary_rate_auto_update_enabled": True,
        "secondary_rate_source_url":          "https://rates.test/oficial",
        "secondary_rate_source_field":        "promedio",
    }


def test_settings_refresh_rate_posts_and_reports_the_new_rate(cli_env, httpx_mock, tmp_config):
    httpx_mock.add_response(
        url=f"{BASE}/settings/secondary-rate/refresh/", method="POST",
        json={"secondary_exchange_rate": "36.42", "secondary_rate_updated_at": "2026-07-29T10:00:00Z"},
    )
    r = runner.invoke(app, ["settings", "refresh-rate"])
    assert r.exit_code == 0, r.stdout
    assert "36.42" in r.stderr or "36.42" in r.stdout


def test_settings_refresh_rate_reports_a_source_failure(cli_env, httpx_mock, tmp_config):
    """
    The server answers 502 with the standard {error, code} envelope, so the
    message reaches the user instead of a bare "Unknown error".
    """
    httpx_mock.add_response(
        url=f"{BASE}/settings/secondary-rate/refresh/", method="POST", status_code=502,
        json={"error": "Rate source returned HTTP 500.", "code": "rate_source_error"},
    )
    r = runner.invoke(app, ["settings", "refresh-rate"])
    assert r.exit_code == 1
    assert "Rate source returned HTTP 500." in r.stderr
