"""
tests/test_auth.py
------------------
Tests for the three public auth endpoints, which now go through
``RetailOpsClient.post_anon`` instead of calling ``httpx.post`` directly.

The migration matters because the raw calls bypassed error-envelope parsing,
verbose logging, and 429 retry. What must NOT change: no Authorization header
is sent, and --url still overrides the profile's base URL.
"""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from retailops_cli.__main__ import app


BASE = "http://test.example/api/v1"

runner = CliRunner()


@pytest.fixture
def cli_env(monkeypatch):
    """A profile with a token, to prove login does not reuse it."""
    monkeypatch.setenv("RETAILOPS_BASE_URL", BASE)
    monkeypatch.setenv("RETAILOPS_TOKEN", "stale-token-that-must-not-be-sent")
    yield


# ── login ─────────────────────────────────────────────────────────────────────


def test_login_posts_credentials_without_an_auth_header(cli_env, httpx_mock, tmp_config):
    httpx_mock.add_response(
        url=f"{BASE}/auth/token/", method="POST",
        json={"token": "new-token", "user_id": 1, "email": "a@b.co", "role_name": "Admin"},
    )
    r = runner.invoke(app, ["auth", "login", "--url", BASE], input="a@b.co\nhunter2\n")
    assert r.exit_code == 0, r.stdout

    req = httpx_mock.get_request()
    assert "Authorization" not in req.headers, "login must not reuse the stored token"
    assert b"a@b.co" in req.content


def test_login_surfaces_a_parsed_error_envelope(cli_env, httpx_mock, tmp_config):
    """
    The API answers bad credentials with 400 + an envelope, not 401. Going
    through the client means that envelope is parsed rather than dumped raw.
    """
    httpx_mock.add_response(
        url=f"{BASE}/auth/token/", method="POST", status_code=400,
        json={
            "error":   "Invalid email or password.",
            "code":    "validation_error",
            "details": {"email": ["Invalid email or password."]},
        },
    )
    r = runner.invoke(app, ["auth", "login", "--url", BASE], input="a@b.co\nwrong\n")
    assert r.exit_code == 1
    assert "Invalid email or password." in r.stderr


def test_login_url_flag_overrides_the_env_base_url(cli_env, httpx_mock, tmp_config):
    other = "http://other.example/api/v1"
    httpx_mock.add_response(
        url=f"{other}/auth/token/", method="POST",
        json={"token": "t", "user_id": 1, "email": "a@b.co", "role_name": None},
    )
    r = runner.invoke(app, ["auth", "login", "--url", other], input="a@b.co\npw\n")
    assert r.exit_code == 0, r.stdout
    assert str(httpx_mock.get_request().url).startswith(other)


# ── password reset ────────────────────────────────────────────────────────────


def test_passwd_reset_posts_email_anonymously(cli_env, httpx_mock, tmp_config):
    httpx_mock.add_response(
        url=f"{BASE}/auth/password-reset/", method="POST",
        json={"detail": "Password reset email sent."},
    )
    r = runner.invoke(app, ["auth", "passwd-reset", "--email", "a@b.co"])
    assert r.exit_code == 0, r.stdout
    assert "Authorization" not in httpx_mock.get_request().headers


def test_passwd_reset_confirm_sends_both_password_fields(cli_env, httpx_mock, tmp_config):
    httpx_mock.add_response(
        url=f"{BASE}/auth/password-reset/confirm/", method="POST",
        json={"detail": "Password has been reset."},
    )
    r = runner.invoke(
        app,
        ["auth", "passwd-reset-confirm", "--uid", "Mg", "--token", "abc123"],
        input="newpassword1\nnewpassword1\n",
    )
    assert r.exit_code == 0, r.stdout
    body = httpx_mock.get_request().content
    assert b"new_password" in body and b"confirm_password" in body


def test_passwd_reset_confirm_rejects_mismatched_passwords(cli_env, no_http, tmp_config):
    r = runner.invoke(
        app,
        ["auth", "passwd-reset-confirm", "--uid", "Mg", "--token", "abc123"],
        input="newpassword1\ndifferent2\n",
    )
    assert r.exit_code == 1
    assert "do not match" in r.stderr


@pytest.fixture
def no_http(httpx_mock):
    """Nothing queued: a request that escapes client-side validation fails."""
    yield httpx_mock
    assert httpx_mock.get_requests() == []
