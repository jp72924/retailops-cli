"""
tests/test_client.py
--------------------
HTTP-level tests for ``RetailOpsClient`` using pytest-httpx.

Coverage:
- Auth header is attached on authenticated methods, absent on post_anon.
- get/post/patch/put/delete dispatch the right HTTP verb and return JSON.
- None-valued query params and body fields are stripped before send.
- 204 responses surface as None.
- Empty bodies surface as None.
- 4xx responses are converted to RetailOpsError with parsed envelope.
- 429 triggers retry up to 3 attempts honoring Retry-After.
- After the retry budget, a final 429 still raises.
"""

from __future__ import annotations

from io import BytesIO

import pytest

from retailops_cli.errors import RetailOpsError


BASE = "http://test.example/api/v1"


# ── auth header ───────────────────────────────────────────────────────────────


def test_auth_header_attached_on_get(client, httpx_mock):
    httpx_mock.add_response(url=f"{BASE}/dashboard/", json={"ok": True})
    client.get("dashboard/")
    req = httpx_mock.get_request()
    assert req.headers["Authorization"] == "Token test-token-abc123"


def test_post_anon_does_not_send_auth_header(client, httpx_mock):
    httpx_mock.add_response(
        url=f"{BASE}/auth/token/",
        method="POST",
        json={"token": "x", "user_id": 1, "email": "a@b.c", "role_name": "Admin"},
    )
    client.post_anon("auth/token/", {"email": "a@b.c", "password": "x"})
    req = httpx_mock.get_request()
    assert "Authorization" not in req.headers


# ── verb dispatch ─────────────────────────────────────────────────────────────


def test_get_returns_parsed_json(client, httpx_mock):
    httpx_mock.add_response(url=f"{BASE}/products/1/", json={"id": 1, "sku": "A"})
    data = client.get("products/1/")
    assert data == {"id": 1, "sku": "A"}


def test_post_dispatches_post(client, httpx_mock):
    httpx_mock.add_response(
        url=f"{BASE}/customers/", method="POST", status_code=201, json={"id": 9},
    )
    data = client.post("customers/", {"first_name": "X", "last_name": "Y"})
    assert data == {"id": 9}
    assert httpx_mock.get_request().method == "POST"


def test_post_multipart_dispatches_file_and_auth(client, httpx_mock):
    httpx_mock.add_response(
        url=f"{BASE}/products/",
        method="POST",
        status_code=201,
        json={"id": 1},
    )
    image = BytesIO(b"image-bytes")
    data = client.post_multipart(
        "products/",
        {"sku": "SKU-1", "is_active": True},
        {"image": ("shoe.jpg", image, "image/jpeg")},
    )
    req = httpx_mock.get_request()
    assert data == {"id": 1}
    assert req.method == "POST"
    assert req.headers["Authorization"] == "Token test-token-abc123"
    assert req.headers["Content-Type"].startswith("multipart/form-data")
    assert b'name="sku"' in req.content
    assert b'name="image"; filename="shoe.jpg"' in req.content


def test_patch_dispatches_patch(client, httpx_mock):
    httpx_mock.add_response(
        url=f"{BASE}/customers/9/", method="PATCH", json={"id": 9, "phone": "555"},
    )
    data = client.patch("customers/9/", {"phone": "555"})
    assert data == {"id": 9, "phone": "555"}
    assert httpx_mock.get_request().method == "PATCH"


def test_patch_multipart_dispatches_file(client, httpx_mock):
    httpx_mock.add_response(
        url=f"{BASE}/products/9/",
        method="PATCH",
        json={"id": 9},
    )
    image = BytesIO(b"new-image")
    data = client.patch_multipart(
        "products/9/",
        {"clear_image": False},
        {"image": ("new.png", image, "image/png")},
    )
    req = httpx_mock.get_request()
    assert data == {"id": 9}
    assert req.method == "PATCH"
    assert req.headers["Content-Type"].startswith("multipart/form-data")
    assert b'name="image"; filename="new.png"' in req.content


def test_put_dispatches_put(client, httpx_mock):
    httpx_mock.add_response(
        url=f"{BASE}/customers/9/", method="PUT", json={"id": 9, "first_name": "X"},
    )
    data = client.put("customers/9/", {"first_name": "X"})
    assert data == {"id": 9, "first_name": "X"}
    assert httpx_mock.get_request().method == "PUT"


def test_delete_dispatches_delete_returns_none(client, httpx_mock):
    httpx_mock.add_response(
        url=f"{BASE}/customers/9/", method="DELETE", status_code=204,
    )
    assert client.delete("customers/9/") is None
    assert httpx_mock.get_request().method == "DELETE"


# ── content edge cases ────────────────────────────────────────────────────────


def test_post_204_returns_none(client, httpx_mock):
    httpx_mock.add_response(
        url=f"{BASE}/auth/token/revoke/", method="POST", status_code=204,
    )
    assert client.post("auth/token/revoke/") is None


def test_get_empty_body_returns_none(client, httpx_mock):
    httpx_mock.add_response(url=f"{BASE}/empty/", content=b"")
    assert client.get("empty/") is None


def test_get_text_returns_raw_body(client, httpx_mock):
    httpx_mock.add_response(
        url=f"{BASE}/schema/?format=json",
        text='{"openapi":"3.0.0"}',
    )
    text = client.get_text("schema/", {"format": "json"}, accept="application/json")
    req = httpx_mock.get_request()
    assert text == '{"openapi":"3.0.0"}'
    assert req.headers["Accept"] == "application/json"


def test_custom_auth_scheme_for_kiosk(profile, httpx_mock):
    from dataclasses import replace
    from retailops_cli.client import RetailOpsClient

    kiosk_profile = replace(profile, token="kiosk-secret")
    httpx_mock.add_response(url=f"{BASE}/kiosk/heartbeat/", method="POST", json={"ok": True})
    with RetailOpsClient(kiosk_profile, auth_scheme="KioskKey") as kiosk_client:
        kiosk_client.post("kiosk/heartbeat/")
    assert httpx_mock.get_request().headers["Authorization"] == "KioskKey kiosk-secret"


# ── path normalisation ────────────────────────────────────────────────────────


def test_leading_slash_is_stripped_from_path(client, httpx_mock):
    """Client should treat '/dashboard/' and 'dashboard/' identically."""
    httpx_mock.add_response(url=f"{BASE}/dashboard/", json={})
    client.get("/dashboard/")
    assert httpx_mock.get_request().url.path == "/api/v1/dashboard/"


# ── None-value stripping ──────────────────────────────────────────────────────


def test_none_query_params_are_stripped(client, httpx_mock):
    httpx_mock.add_response(url=f"{BASE}/products/?stock=low", json={"results": []})
    client.get("products/", {"stock": "low", "category": None, "search": None})
    qs = dict(httpx_mock.get_request().url.params)
    assert qs == {"stock": "low"}


def test_none_body_fields_are_stripped(client, httpx_mock):
    import json as _json

    httpx_mock.add_response(url=f"{BASE}/customers/", method="POST", json={"id": 1})
    client.post("customers/", {"first_name": "X", "phone": None, "notes": None})
    body = _json.loads(httpx_mock.get_request().content)
    assert body == {"first_name": "X"}


# ── error envelope ────────────────────────────────────────────────────────────


def test_4xx_raises_retailops_error_with_envelope(client, httpx_mock):
    httpx_mock.add_response(
        url=f"{BASE}/customers/",
        method="POST",
        status_code=400,
        json={
            "error":   "Validation failed.",
            "code":    "validation_error",
            "details": {"email": ["Already exists."]},
        },
    )
    with pytest.raises(RetailOpsError) as excinfo:
        client.post("customers/", {"email": "x@y.z"})
    e = excinfo.value
    assert e.status == 400
    assert e.code == "validation_error"
    assert e.details == {"email": ["Already exists."]}


def test_non_json_error_body_falls_back_to_http_error(client, httpx_mock):
    httpx_mock.add_response(
        url=f"{BASE}/products/", status_code=502, text="Bad Gateway",
    )
    with pytest.raises(RetailOpsError) as excinfo:
        client.get("products/")
    e = excinfo.value
    assert e.status == 502
    assert e.code == "http_error"
    assert "Bad Gateway" in e.error


# ── 429 retry ─────────────────────────────────────────────────────────────────


def test_429_retried_then_succeeds(client, httpx_mock, fast_retry):
    """Two 429s followed by a 200 should succeed transparently."""
    httpx_mock.add_response(
        url=f"{BASE}/products/", status_code=429, headers={"Retry-After": "1"},
    )
    httpx_mock.add_response(
        url=f"{BASE}/products/", status_code=429, headers={"Retry-After": "1"},
    )
    httpx_mock.add_response(url=f"{BASE}/products/", json={"results": []})

    data = client.get("products/")
    assert data == {"results": []}
    assert len(httpx_mock.get_requests()) == 3


def test_429_after_max_retries_raises(client, httpx_mock, fast_retry):
    """Three consecutive 429s exhaust the retry budget and raise."""
    for _ in range(3):
        httpx_mock.add_response(
            url=f"{BASE}/products/", status_code=429, headers={"Retry-After": "1"},
        )
    with pytest.raises(RetailOpsError) as excinfo:
        client.get("products/")
    assert excinfo.value.status == 429


# ── context-manager support ───────────────────────────────────────────────────


def test_client_works_as_context_manager(profile, httpx_mock):
    from retailops_cli.client import RetailOpsClient

    httpx_mock.add_response(url=f"{BASE}/dashboard/", json={})
    with RetailOpsClient(profile) as c:
        c.get("dashboard/")
