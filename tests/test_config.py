"""
tests/test_config.py
--------------------
Profile resolution, env-var overrides, and TOML round-trip for config.py.
"""

from __future__ import annotations

import tomllib

import pytest

from retailops_cli import config


# ── load_config ───────────────────────────────────────────────────────────────


def test_load_config_returns_defaults_when_file_missing(tmp_config):
    """A missing config file produces a sensible default dict, not an error."""
    assert not tmp_config.exists()
    cfg = config.load_config()
    assert cfg["profiles"] == {}
    assert cfg["settings"]["active_profile"] == "default"


def test_save_then_load_round_trip(tmp_config):
    payload = {
        "profiles": {
            "default": {"base_url": "http://x/api/v1", "token": "abc", "timeout": 30},
        },
        "settings": {"active_profile": "default"},
    }
    config.save_config(payload)
    assert tmp_config.exists()

    re_read = config.load_config()
    assert re_read == payload


# ── Profile resolution chain ──────────────────────────────────────────────────


def test_get_profile_uses_explicit_name_argument(tmp_config):
    config.save_config({
        "profiles": {
            "prod": {"base_url": "https://prod/api/v1", "token": "PROD"},
            "default": {"base_url": "http://local/api/v1", "token": "LOCAL"},
        },
        "settings": {"active_profile": "default"},
    })
    p = config.get_profile("prod")
    assert p.name == "prod"
    assert p.base_url == "https://prod/api/v1"
    assert p.token == "PROD"


def test_get_profile_uses_env_var_when_no_argument(tmp_config, monkeypatch):
    config.save_config({
        "profiles": {
            "staging": {"base_url": "https://stg/api/v1", "token": "STG"},
            "default": {"base_url": "http://local/api/v1", "token": "LOCAL"},
        },
        "settings": {"active_profile": "default"},
    })
    monkeypatch.setenv("RETAILOPS_PROFILE", "staging")
    p = config.get_profile()
    assert p.name == "staging"
    assert p.token == "STG"


def test_get_profile_falls_back_to_active_profile_setting(tmp_config):
    config.save_config({
        "profiles": {
            "active-one": {"base_url": "http://a/api/v1", "token": "AAA"},
        },
        "settings": {"active_profile": "active-one"},
    })
    p = config.get_profile()
    assert p.name == "active-one"
    assert p.token == "AAA"


def test_get_profile_default_when_nothing_configured(tmp_config):
    """No config file, no env var: should still return a Profile named 'default'."""
    p = config.get_profile()
    assert p.name == "default"
    # Token is empty when nothing is stored.
    assert p.token == ""
    # Base URL falls through to the documented dev default.
    assert p.base_url == "http://127.0.0.1:8000/api/v1"


# ── env-var overrides ─────────────────────────────────────────────────────────


def test_env_token_override_wins(tmp_config, monkeypatch):
    config.save_config({
        "profiles": {"default": {"base_url": "http://x/api/v1", "token": "FROM_FILE"}},
        "settings": {"active_profile": "default"},
    })
    monkeypatch.setenv("RETAILOPS_TOKEN", "FROM_ENV")
    p = config.get_profile()
    assert p.token == "FROM_ENV"


def test_env_base_url_override_wins(tmp_config, monkeypatch):
    config.save_config({
        "profiles": {"default": {"base_url": "http://x/api/v1", "token": "T"}},
        "settings": {"active_profile": "default"},
    })
    monkeypatch.setenv("RETAILOPS_BASE_URL", "https://override.example/api/v1")
    p = config.get_profile()
    assert p.base_url == "https://override.example/api/v1"


def test_get_profile_strips_trailing_slash_from_base_url(tmp_config):
    config.save_config({
        "profiles": {"default": {"base_url": "http://x/api/v1/", "token": "T"}},
        "settings": {"active_profile": "default"},
    })
    p = config.get_profile()
    assert p.base_url == "http://x/api/v1"


# ── set_profile_token / remove_profile_token / set_active_profile ─────────────


def test_set_profile_token_creates_first_profile_active(tmp_config):
    config.set_profile_token("default", "TOK", "http://h/api/v1", timeout=15.0)
    raw = tomllib.loads(tmp_config.read_text())
    assert raw["profiles"]["default"]["token"] == "TOK"
    assert raw["profiles"]["default"]["base_url"] == "http://h/api/v1"
    assert raw["profiles"]["default"]["timeout"] == 15.0
    assert raw["settings"]["active_profile"] == "default"


def test_set_profile_token_named_default_is_always_active(tmp_config):
    config.set_profile_token("staging", "S1", "http://s/api/v1")
    config.set_profile_token("default", "D1", "http://d/api/v1")
    raw = tomllib.loads(tmp_config.read_text())
    # Per the policy: writing to "default" sets active to "default".
    assert raw["settings"]["active_profile"] == "default"


def test_set_active_profile(tmp_config):
    config.set_profile_token("default", "D", "http://d/api/v1")
    config.set_profile_token("prod",    "P", "http://p/api/v1")
    config.set_active_profile("prod")
    raw = tomllib.loads(tmp_config.read_text())
    assert raw["settings"]["active_profile"] == "prod"


def test_remove_profile_token_clears_token_keeps_profile_entry(tmp_config):
    config.set_profile_token("default", "TOK", "http://h/api/v1")
    config.remove_profile_token("default")
    raw = tomllib.loads(tmp_config.read_text())
    assert "default" in raw["profiles"]
    assert "token" not in raw["profiles"]["default"]


def test_remove_profile_token_is_silent_for_unknown_profile(tmp_config):
    config.set_profile_token("default", "TOK", "http://h/api/v1")
    # Should not raise.
    config.remove_profile_token("does-not-exist")
    raw = tomllib.loads(tmp_config.read_text())
    assert raw["profiles"]["default"]["token"] == "TOK"
