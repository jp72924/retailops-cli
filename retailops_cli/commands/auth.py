"""
commands/auth.py
----------------
Authentication and profile management commands.

  retailops-cli auth login                 — prompt for credentials, store token in config
  retailops-cli auth logout                — revoke token, remove from config
  retailops-cli auth whoami                — show authenticated identity (calls /auth/me/)
  retailops-cli auth config                — show resolved profile / URL / token / env overrides
  retailops-cli auth profiles              — list configured profiles
  retailops-cli auth use                   — set the active profile
  retailops-cli auth passwd-reset          — request a password-reset link (public)
  retailops-cli auth passwd-reset-confirm  — complete a password reset using uid + token (public)
"""

from __future__ import annotations

import httpx
import typer

from .. import state
from ..config import (
    CONFIG_PATH,
    get_profile,
    load_config,
    remove_profile_token,
    save_config,
    set_active_profile,
    set_profile_token,
)
from ..errors import RetailOpsError, handle_error, handle_connection_error, raise_for_status
from ..output import console, err_console, print_info, print_success

app = typer.Typer(no_args_is_help=True)


@app.command()
def login(
    url: str = typer.Option(
        "http://127.0.0.1:8000/api/v1",
        "--url", "-u",
        help="API base URL for this profile.",
    ),
    profile: str = typer.Option(
        "default",
        "--profile", "-p",
        help="Profile name to save the token under.",
    ),
) -> None:
    """Authenticate and save the token to a config profile."""
    email    = typer.prompt("Email")
    password = typer.prompt("Password", hide_input=True)

    base = url.rstrip("/")
    try:
        r = httpx.post(
            f"{base}/auth/token/",
            json={"email": email, "password": password},
            headers={"Accept": "application/json", "Content-Type": "application/json"},
            timeout=30,
        )
        raise_for_status(r)
        data = r.json()
    except RetailOpsError as e:
        handle_error(e)
        return
    except httpx.ConnectError as e:
        handle_connection_error(e, base)
        return

    set_profile_token(profile, data["token"], base)
    role = data.get("role_name") or "no role assigned"
    print_success(f"Logged in as [bold]{data['email']}[/bold] ({role}).")
    print_info(f"Token saved to profile '{profile}' in {CONFIG_PATH}")


@app.command()
def logout(
    profile: str = typer.Option(None, "--profile", "-p", help="Profile to log out from."),
) -> None:
    """Revoke the active token and remove it from the config."""
    prof = get_profile(profile or state.profile)
    if not prof.token:
        console.print("[yellow]No token found for this profile.[/yellow]")
        raise typer.Exit(0)

    from ..client import RetailOpsClient
    try:
        with RetailOpsClient(prof, verbose=state.verbose) as client:
            client.post("auth/token/revoke/")
    except RetailOpsError as e:
        if e.status not in (401, 403):
            # A 401 just means the token was already invalid — that's fine.
            handle_error(e)
    except httpx.ConnectError:
        pass  # Server unreachable but we can still clear the local token.

    remove_profile_token(prof.name)
    print_success(f"Logged out. Token removed from profile '{prof.name}'.")


@app.command()
def whoami() -> None:
    """Display the authenticated user identity and role.

    Calls GET /auth/me/ to fetch the server-side identity associated with
    the current profile's token, then prints email, name, role, and the
    local profile/URL/token for reference. A 401 means the stored token
    is invalid or expired — re-run `retailops-cli auth login`.
    """
    prof = get_profile(state.profile)
    if not prof.token:
        err_console.print(
            "[red]Not authenticated.[/red] Run [bold]retailops-cli auth login[/bold] first."
        )
        raise typer.Exit(2)

    from ..client import RetailOpsClient
    try:
        with RetailOpsClient(prof, verbose=state.verbose) as client:
            me = client.get("auth/me/")
    except RetailOpsError as e:
        handle_error(e)
        return
    except httpx.ConnectError as e:
        handle_connection_error(e, prof.base_url)
        return

    full_name = f"{me.get('first_name', '')} {me.get('last_name', '')}".strip() or "-"
    role_name = me.get('role_name') or "-"
    active_marker = "" if me.get('is_active', True) else " [yellow](inactive)[/yellow]"

    console.print(f"  [bold]User    :[/bold] {me.get('email', '?')} (id={me.get('user_id', '?')}){active_marker}")
    console.print(f"  [bold]Name    :[/bold] {full_name}")
    console.print(f"  [bold]Role    :[/bold] {role_name}")
    console.print(f"  [bold]Profile :[/bold] {prof.name}")
    console.print(f"  [bold]Base URL:[/bold] {prof.base_url}")
    token_preview = f"{prof.token[:8]}..." if len(prof.token) > 8 else prof.token
    console.print(f"  [bold]Token   :[/bold] {token_preview}")


@app.command(name="config")
def show_config() -> None:
    """Show the resolved CLI configuration: profile, URL, token preview, and any env-var overrides currently in effect.

    Useful for diagnosing "why is retailops-cli talking to the wrong server / using the wrong token" issues.
    """
    import os

    cfg = load_config()
    active = cfg.get("settings", {}).get("active_profile", "default")

    # Replicate the resolution chain from get_profile() so we can label each source.
    flag_profile = state.profile
    env_profile  = os.environ.get("RETAILOPS_PROFILE")
    if flag_profile:
        profile_name, profile_source = flag_profile, "--profile flag"
    elif env_profile:
        profile_name, profile_source = env_profile, "RETAILOPS_PROFILE env var"
    elif active:
        profile_name, profile_source = active, "settings.active_profile"
    else:
        profile_name, profile_source = "default", "fallback default"

    prof = get_profile(state.profile)

    env_token    = os.environ.get("RETAILOPS_TOKEN")
    env_base_url = os.environ.get("RETAILOPS_BASE_URL")

    file_data = cfg.get("profiles", {}).get(profile_name, {})
    base_source = "RETAILOPS_BASE_URL env var" if env_base_url else (
        "config file" if file_data.get("base_url") else "fallback default"
    )
    token_source = "RETAILOPS_TOKEN env var" if env_token else (
        "config file" if file_data.get("token") else "(none)"
    )

    token_display = (
        f"{prof.token[:8]}..." if len(prof.token) > 8
        else (prof.token or "[dim](not set)[/dim]")
    )

    from rich.table import Table
    tbl = Table(show_header=False, box=None, pad_edge=False, show_edge=False)
    tbl.add_column("Field", style="bold", min_width=18, no_wrap=True)
    tbl.add_column("Value")
    tbl.add_column("Source", style="dim")

    tbl.add_row("Profile",    profile_name,   profile_source)
    tbl.add_row("Base URL",   prof.base_url,  base_source)
    tbl.add_row("Token",      token_display,  token_source)
    tbl.add_row("Timeout",    f"{prof.timeout}s", "config file" if file_data.get("timeout") else "default")
    tbl.add_row("Verify SSL", "Yes" if prof.verify_ssl else "No", "config file")
    tbl.add_row("Config path", str(CONFIG_PATH), "")

    console.print(tbl)


@app.command()
def profiles() -> None:
    """List all configured profiles."""
    cfg    = load_config()
    active = cfg.get("settings", {}).get("active_profile", "default")
    profs  = cfg.get("profiles", {})

    if not profs:
        console.print(
            "[dim]No profiles configured. Run [bold]retailops-cli auth login[/bold] to create one.[/dim]"
        )
        raise typer.Exit(0)

    from rich.table import Table
    tbl = Table(show_header=True, header_style="bold", box=None, pad_edge=False, show_edge=False)
    tbl.add_column("Profile")
    tbl.add_column("Base URL")
    tbl.add_column("Token")
    tbl.add_column("Active", justify="center")

    for name, data in profs.items():
        token = data.get("token", "")
        token_display = f"{token[:8]}…" if len(token) > 8 else ("[dim]—[/dim]" if not token else token)
        is_active = "[green]✓[/green]" if name == active else ""
        tbl.add_row(name, data.get("base_url", ""), token_display, is_active)

    console.print(tbl)


@app.command(name="use")
def use_profile(
    name: str = typer.Argument(..., help="Profile name to activate."),
) -> None:
    """Set the active profile."""
    cfg = load_config()
    if name not in cfg.get("profiles", {}):
        err_console.print(
            f"[red]Profile '{name}' not found.[/red] "
            "Run [bold]retailops-cli auth profiles[/bold] to see available profiles."
        )
        raise typer.Exit(1)
    set_active_profile(name)
    print_success(f"Active profile set to '{name}'.")


# ── password reset helpers ────────────────────────────────────────────────────

def _resolve_base(url_override: str | None) -> str:
    """Return the API base URL: explicit override first, then the active profile."""
    if url_override:
        return url_override.rstrip("/")
    return get_profile(state.profile).base_url.rstrip("/")


# ── passwd-reset ──────────────────────────────────────────────────────────────

@app.command(name="passwd-reset")
def passwd_reset(
    email: str           = typer.Option(...,  "--email", "-e",
                                        prompt=True, help="Email address of the account to reset."),
    url:   str | None    = typer.Option(None, "--url",   "-u",
                                        help="API base URL. Defaults to the active profile's URL."),
) -> None:
    """
    Request a password-reset link for an account.

    This endpoint is public — no authentication token is required.
    In development, the reset link is printed to the Django server terminal
    rather than sent by email. Rate limited to 5 requests per minute.

    \b
    Example:
      retailops-cli auth passwd-reset --email jane@example.com
    """
    base = _resolve_base(url)
    try:
        r = httpx.post(
            f"{base}/auth/password-reset/",
            json={"email": email},
            headers={"Accept": "application/json", "Content-Type": "application/json"},
            timeout=30,
        )
        raise_for_status(r)
        data = r.json()
    except RetailOpsError as e:
        handle_error(e)
        return
    except httpx.ConnectError as e:
        handle_connection_error(e, base)
        return
    print_success(data.get("detail", "Password reset email sent."))


# ── passwd-reset-confirm ──────────────────────────────────────────────────────

@app.command(name="passwd-reset-confirm")
def passwd_reset_confirm(
    uid:   str        = typer.Option(...,  "--uid",   help="Base64 user ID from the reset link."),
    token: str        = typer.Option(...,  "--token", help="One-time reset token from the reset link."),
    url:   str | None = typer.Option(None, "--url",   "-u",
                                     help="API base URL. Defaults to the active profile's URL."),
) -> None:
    """
    Complete a password reset using the uid and token from the reset link.

    This endpoint is public — no authentication token is required.
    Copy the uid and token from the reset URL printed by the server (development)
    or the reset email (production).

    \b
    Example:
      retailops-cli auth passwd-reset-confirm --uid Mg --token abc123-xyz456
    """
    new_password = typer.prompt("New password",     hide_input=True)
    confirm      = typer.prompt("Confirm password", hide_input=True)
    if new_password != confirm:
        err_console.print("[red]Passwords do not match.[/red]")
        raise typer.Exit(1)

    base = _resolve_base(url)
    try:
        r = httpx.post(
            f"{base}/auth/password-reset/confirm/",
            json={
                "uid":              uid,
                "token":            token,
                "new_password":     new_password,
                "confirm_password": confirm,
            },
            headers={"Accept": "application/json", "Content-Type": "application/json"},
            timeout=30,
        )
        raise_for_status(r)
        data = r.json()
    except RetailOpsError as e:
        handle_error(e)
        return
    except httpx.ConnectError as e:
        handle_connection_error(e, base)
        return
    print_success(data.get("detail", "Password has been reset successfully."))
