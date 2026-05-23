from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from retailops_cli.__main__ import app


BASE = "http://test.example/api/v1"
TOKEN = "test-token-abc123"
KIOSK_KEY = "kiosk-key-abc123"

runner = CliRunner()


@pytest.fixture
def cli_env(monkeypatch):
    monkeypatch.setenv("RETAILOPS_BASE_URL", BASE)
    monkeypatch.setenv("RETAILOPS_TOKEN", TOKEN)
    monkeypatch.setenv("RETAILOPS_KIOSK_API_KEY", KIOSK_KEY)
    yield


def _image(workspace_tmp_path, name="receipt.jpg"):
    path = workspace_tmp_path / name
    path.write_bytes(b"fake-image")
    return path


def test_product_create_with_image_uses_multipart(cli_env, httpx_mock, tmp_config, workspace_tmp_path):
    img = _image(workspace_tmp_path, "shoe.jpg")
    httpx_mock.add_response(
        url=f"{BASE}/products/",
        method="POST",
        status_code=201,
        json={"id": 1, "sku": "SKU-1", "name": "Shoe"},
    )

    r = runner.invoke(app, [
        "products", "create",
        "--sku", "SKU-1",
        "--name", "Shoe",
        "--category-id", "2",
        "--unit", "piece",
        "--price", "9.99",
        "--external-image-url", "https://example.test/shoe.jpg",
        "--image", str(img),
    ])

    assert r.exit_code == 0, r.stdout
    req = httpx_mock.get_request()
    assert req.headers["Authorization"] == f"Token {TOKEN}"
    assert req.headers["Content-Type"].startswith("multipart/form-data")
    assert b'name="image"; filename="shoe.jpg"' in req.content
    assert b'name="external_image_url"' in req.content


def test_product_update_clear_image_uses_json(cli_env, httpx_mock, tmp_config):
    httpx_mock.add_response(
        url=f"{BASE}/products/3/",
        method="PATCH",
        json={"id": 3, "has_image": False},
    )

    r = runner.invoke(app, [
        "products", "update", "3",
        "--clear-image",
        "--clear-external-image-url",
    ])

    assert r.exit_code == 0, r.stdout
    body = json.loads(httpx_mock.get_request().content)
    assert body == {"external_image_url": "", "clear_image": True}


def test_payment_record_with_receipt_image_uses_multipart(cli_env, httpx_mock, tmp_config, workspace_tmp_path):
    img = _image(workspace_tmp_path, "receipt.png")
    httpx_mock.add_response(
        url=f"{BASE}/payments/",
        method="POST",
        status_code=201,
        json={
            "id": 9,
            "payment_number": "PAY-1",
            "amount": "1.98",
            "payment_method": "mobile_payment",
        },
    )

    r = runner.invoke(app, [
        "payments", "record",
        "--order", "7",
        "--amount", "1.98",
        "--method", "mobile_payment",
        "--ref", "005901670379",
        "--transaction-key", "txn-1",
        "--origin-bank", "BDV",
        "--recipient-bank", "Bancamiga",
        "--receipt-image", str(img),
        "--ocr-data", '{"payment":{"reference":"005901670379"}}',
    ])

    assert r.exit_code == 0, r.stdout
    req = httpx_mock.get_request()
    assert req.headers["Content-Type"].startswith("multipart/form-data")
    assert b'name="receipt_image"; filename="receipt.png"' in req.content
    assert b'name="payment_method"' in req.content
    assert b"mobile_payment" in req.content
    assert b"ocr_receipt_data" in req.content


def test_payment_list_passes_modern_filters(cli_env, httpx_mock, tmp_config):
    httpx_mock.add_response(
        url=(
            f"{BASE}/payments/?sales_order=7&payment_method=mobile_payment"
            "&status=pending_review&has_receipt=true&bank=BDV&page=1&page_size=25"
        ),
        json={"count": 0, "results": []},
    )

    r = runner.invoke(app, [
        "payments", "list",
        "--order", "7",
        "--payment-method", "mobile_payment",
        "--status", "pending_review",
        "--has-receipt",
        "--bank", "BDV",
    ])

    assert r.exit_code == 0, r.stdout


def test_verify_receipt_posts_expected_fields(cli_env, httpx_mock, tmp_config, workspace_tmp_path):
    img = _image(workspace_tmp_path, "receipt.jpg")
    httpx_mock.add_response(
        url=f"{BASE}/payments/receipts/verify/",
        method="POST",
        json={"valid": True, "checks": {"field_matches": {}}, "warnings": []},
    )

    r = runner.invoke(app, [
        "payments", "verify-receipt",
        "--image", str(img),
        "--method", "bank_transfer",
        "--expected-amount-usd", "1.98",
        "--expected-reference", "061235765636",
        "--expected-paid-on", "2026-05-03",
        "--expected-origin-bank", "Banesco",
    ])

    assert r.exit_code == 0, r.stdout
    req = httpx_mock.get_request()
    assert req.headers["Content-Type"].startswith("multipart/form-data")
    assert b'name="image"; filename="receipt.jpg"' in req.content
    assert b"expected_amount_usd" in req.content
    assert b"Banesco" in req.content


def test_settings_update_sends_ocr_fields(cli_env, httpx_mock, tmp_config):
    httpx_mock.add_response(
        url=f"{BASE}/settings/",
        method="PATCH",
        json={"ocr_enabled": True, "ocr_enabled_methods": ["mobile_payment", "bank_transfer"]},
    )

    r = runner.invoke(app, [
        "settings", "update",
        "--ocr-enabled",
        "--ocr-base-url", "https://vepay.example.test",
        "--ocr-timeout-seconds", "20",
        "--ocr-enabled-method", "mobile_payment",
        "--ocr-enabled-method", "bank_transfer",
        "--receipt-image-required",
    ])

    assert r.exit_code == 0, r.stdout
    body = json.loads(httpx_mock.get_request().content)
    assert body["ocr_enabled"] is True
    assert body["ocr_base_url"] == "https://vepay.example.test"
    assert body["ocr_timeout_seconds"] == 20
    assert body["ocr_enabled_methods"] == ["mobile_payment", "bank_transfer"]
    assert body["receipt_image_required_for_receipt_methods"] is True
    assert "ocr_api_key" not in body


def test_settings_clear_ocr_api_key_is_explicit(cli_env, httpx_mock, tmp_config):
    httpx_mock.add_response(url=f"{BASE}/settings/", method="PATCH", json={"ocr_api_key": ""})
    r = runner.invoke(app, ["settings", "update", "--clear-ocr-api-key"])
    assert r.exit_code == 0, r.stdout
    assert json.loads(httpx_mock.get_request().content) == {"ocr_api_key": ""}


def test_kiosk_heartbeat_uses_kiosk_key(cli_env, httpx_mock, tmp_config):
    httpx_mock.add_response(
        url=f"{BASE}/kiosk/heartbeat/",
        method="POST",
        json={"station": "DEV / 1", "is_active": True},
    )

    r = runner.invoke(app, ["kiosk", "heartbeat"])

    assert r.exit_code == 0, r.stdout
    assert httpx_mock.get_request().headers["Authorization"] == f"KioskKey {KIOSK_KEY}"


def test_kiosk_checkout_posts_json_payload(cli_env, httpx_mock, tmp_config):
    httpx_mock.add_response(
        url=f"{BASE}/kiosk/checkout/",
        method="POST",
        status_code=201,
        json={"order_id": 10, "payment_number": "PAY-10"},
    )

    r = runner.invoke(app, [
        "kiosk", "checkout",
        "--customer-id", "5",
        "--items", '[{"sku":"SKU-1","quantity":2}]',
        "--payment-reference", "REF-1",
        "--payment-method", "mobile_payment",
        "--receipt", '{"reference":"REF-1","paid_on":"2026-05-03"}',
    ])

    assert r.exit_code == 0, r.stdout
    body = json.loads(httpx_mock.get_request().content)
    assert body["items"] == [{"sku": "SKU-1", "quantity": 2}]
    assert body["receipt"]["paid_on"] == "2026-05-03"
    assert body["payment_method"] == "mobile_payment"


def test_schema_get_prints_raw_json(cli_env, httpx_mock, tmp_config):
    httpx_mock.add_response(
        url=f"{BASE}/schema/?format=json",
        text='{"openapi":"3.0.0"}',
    )

    r = runner.invoke(app, ["schema", "get", "--format", "json"])

    assert r.exit_code == 0, r.stdout
    assert '{"openapi":"3.0.0"}' in r.stdout
    assert httpx_mock.get_request().headers["Accept"] == "application/json"
