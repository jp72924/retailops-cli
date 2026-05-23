"""
tests/conftest.py
-----------------
Shared pytest fixtures for the retailops-cli test suite.

Goals:
- Hermetic config: every test that touches config gets a tmp config file via
  ``tmp_config`` and never reads or writes the developer's real
  ``%APPDATA%\\retailops\\config.toml`` (or ``~/.config/retailops/config.toml``).
- Hermetic env: ``clean_env`` strips RETAILOPS_* env vars so a developer's
  shell can't influence test outcomes.
- A ready-made ``profile`` and ``client`` for HTTP-level tests, paired with
  the ``httpx_mock`` fixture from pytest-httpx for request/response control.
"""

from __future__ import annotations

import shutil
import uuid
from pathlib import Path

import pytest

from retailops_cli import config as _config_mod
from retailops_cli.config import Profile


# ── env-var hygiene ───────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    """Ensure RETAILOPS_* env vars from the dev shell don't leak into tests."""
    for name in ("RETAILOPS_PROFILE", "RETAILOPS_TOKEN", "RETAILOPS_BASE_URL"):
        monkeypatch.delenv(name, raising=False)
    yield


# ── tmp-config redirection ────────────────────────────────────────────────────


@pytest.fixture
def workspace_tmp_path(request) -> Path:
    """
    Test-local temp directory created without pytest's 0o700 tmp_path mode.

    In this Windows workspace, directories created with mode 0o700 can become
    inaccessible to the current user, so CLI tests use this fixture for scratch
    files instead of pytest's built-in tmp_path fixture.
    """
    base = Path(__file__).resolve().parents[1] / "test_tmp"
    base.mkdir(exist_ok=True)
    safe_name = "".join(ch if ch.isalnum() else "_" for ch in request.node.name)
    path = base / f"{safe_name}_{uuid.uuid4().hex}"
    path.mkdir()
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


@pytest.fixture
def tmp_config(workspace_tmp_path: Path, monkeypatch) -> Path:
    """
    Redirect ``retailops_cli.config.CONFIG_PATH`` at the module level so that
    every load_config / save_config call in the test reads from tmp_path.
    Returns the (possibly non-existent) path to the redirected file.
    """
    fake = workspace_tmp_path / "config.toml"
    monkeypatch.setattr(_config_mod, "CONFIG_PATH", fake)
    return fake


# ── HTTP-level fixtures ───────────────────────────────────────────────────────


@pytest.fixture
def profile() -> Profile:
    """A fixed Profile for client tests; the URL is what httpx_mock will match."""
    return Profile(
        name="test",
        base_url="http://test.example/api/v1",
        token="test-token-abc123",
        timeout=5.0,
        verify_ssl=False,
    )


@pytest.fixture
def client(profile):
    """A live RetailOpsClient bound to the test profile, closed at teardown."""
    from retailops_cli.client import RetailOpsClient

    c = RetailOpsClient(profile, verbose=False)
    try:
        yield c
    finally:
        c.close()


@pytest.fixture
def fast_retry(monkeypatch):
    """Replace time.sleep inside client.py so 429-retry tests don't actually sleep."""
    from retailops_cli import client as _client_mod

    monkeypatch.setattr(_client_mod.time, "sleep", lambda *_a, **_kw: None)
