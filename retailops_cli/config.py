"""
retailops_cli.config
--------------------
Config file management for the RetailOps CLI.

Config file location:
  Windows : %APPDATA%\\retailops\\config.toml
  Linux/Mac: ~/.config/retailops/config.toml  (respects $XDG_CONFIG_HOME)

Profile resolution order (first match wins):
  1. --profile flag (passed as argument to get_profile())
  2. RETAILOPS_PROFILE environment variable
  3. settings.active_profile in config file
  4. "default"

Token / URL overrides (useful in CI):
  RETAILOPS_TOKEN    overrides the stored token for the resolved profile
  RETAILOPS_BASE_URL overrides the stored base_url for the resolved profile

Example config.toml:
  [profiles.default]
  base_url = "http://127.0.0.1:8000/api/v1"
  token    = "9944b09199c62bcf9418ad846dd0e4bbdfc6ee4b"
  timeout  = 30

  [profiles.prod]
  base_url = "https://api.example.com/api/v1"
  token    = "..."

  [settings]
  active_profile = "default"
  output_format  = "table"
  page_size      = 25
"""

from __future__ import annotations

import os
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

import tomli_w


def _config_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home()))
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    d = base / "retailops"
    d.mkdir(parents=True, exist_ok=True)
    return d


CONFIG_PATH: Path = _config_dir() / "config.toml"

_DEFAULT_CONFIG: dict = {
    "profiles": {},
    "settings": {
        "active_profile": "default",
        "output_format": "table",
        "page_size": 25,
    },
}


@dataclass
class Profile:
    name: str
    base_url: str
    token: str
    timeout: float = 30.0
    verify_ssl: bool = True


# ── low-level load / save ─────────────────────────────────────────────────────

def load_config() -> dict:
    """Return the full config dict. Returns defaults if the file doesn't exist."""
    if not CONFIG_PATH.exists():
        return {
            "profiles": {},
            "settings": {
                "active_profile": "default",
                "output_format": "table",
                "page_size": 25,
            },
        }
    with open(CONFIG_PATH, "rb") as fh:
        return tomllib.load(fh)


def save_config(cfg: dict) -> None:
    """Write the config dict to disk as TOML."""
    with open(CONFIG_PATH, "wb") as fh:
        tomli_w.dump(cfg, fh)


# ── profile helpers ───────────────────────────────────────────────────────────

def get_profile(name: str | None = None) -> Profile:
    """
    Resolve and return the active Profile.

    Args:
        name: Explicit profile name (from --profile flag). None = auto-resolve.
    """
    cfg = load_config()
    profile_name = (
        name
        or os.environ.get("RETAILOPS_PROFILE")
        or cfg.get("settings", {}).get("active_profile", "default")
        or "default"
    )

    data: dict = cfg.get("profiles", {}).get(profile_name, {})

    # Environment variable overrides take priority over stored values.
    token    = os.environ.get("RETAILOPS_TOKEN")    or data.get("token", "")
    base_url = os.environ.get("RETAILOPS_BASE_URL") or data.get("base_url", "http://127.0.0.1:8000/api/v1")

    return Profile(
        name=profile_name,
        base_url=base_url.rstrip("/"),
        token=token,
        timeout=float(data.get("timeout", 30)),
        verify_ssl=bool(data.get("verify_ssl", True)),
    )


def set_profile_token(profile_name: str, token: str, base_url: str, timeout: float = 30.0) -> None:
    """Write or update a profile entry in the config file."""
    cfg = load_config()
    if "profiles" not in cfg:
        cfg["profiles"] = {}
    cfg["profiles"][profile_name] = {
        "base_url": base_url.rstrip("/"),
        "token": token,
        "timeout": timeout,
        "verify_ssl": True,
    }
    if "settings" not in cfg:
        cfg["settings"] = {}
    # Make this profile active if it's the first, or if it's "default".
    existing_profiles = [p for p in cfg["profiles"] if cfg["profiles"][p].get("token")]
    if len(existing_profiles) == 1 or profile_name == "default":
        cfg["settings"]["active_profile"] = profile_name
    save_config(cfg)


def remove_profile_token(profile_name: str) -> None:
    """Clear the token from a profile (does not delete the profile entry)."""
    cfg = load_config()
    if profile_name in cfg.get("profiles", {}):
        cfg["profiles"][profile_name].pop("token", None)
        save_config(cfg)


def set_active_profile(profile_name: str) -> None:
    """Update settings.active_profile in the config file."""
    cfg = load_config()
    if "settings" not in cfg:
        cfg["settings"] = {}
    cfg["settings"]["active_profile"] = profile_name
    save_config(cfg)
