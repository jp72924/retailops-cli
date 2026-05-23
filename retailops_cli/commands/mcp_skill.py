"""
commands/mcp_skill.py
---------------------
  retailops-cli mcp-skill [--markdown] [--url URL]

Returns the MCP skill card — a structured capability descriptor for the
RetailOps MCP server. Public endpoint; no authentication token required.

Two response formats are available:
  - JSON (default): full structured document; compatible with --output json / jq
  - Markdown (--markdown): human-readable prose; printed directly to stdout
"""

from __future__ import annotations

import sys
from typing import Optional

import httpx
import typer

from .. import state
from ..config import get_profile
from ..errors import RetailOpsError, handle_error, handle_connection_error, raise_for_status
from ..output import render


def _resolve_base(url_override: str | None) -> str:
    """Return the API base URL: explicit override first, then the active profile."""
    if url_override:
        return url_override.rstrip("/")
    return get_profile(state.profile).base_url.rstrip("/")


def mcp_skill_command(
    markdown: bool        = typer.Option(False, "--markdown", "-m", is_flag=True,
                                          help="Return the skill card as Markdown prose instead of JSON."),
    url:      str | None  = typer.Option(None, "--url", "-u",
                                          help="API base URL. Defaults to the active profile's URL."),
    output:   Optional[str] = typer.Option(None, "--output", "-o"),
) -> None:
    """
    Retrieve the MCP skill card for the RetailOps MCP server.

    The skill card is a structured capability descriptor: all tools, resources,
    workflow prompts, the order lifecycle, constraints, and error codes.

    This endpoint is public — no authentication token is required.

    \b
    Examples:
      retailops-cli mcp-skill                         # JSON to stdout
      retailops-cli mcp-skill --output json | jq .tools
      retailops-cli mcp-skill --markdown              # Markdown prose to stdout
      retailops-cli mcp-skill --markdown > SKILL.md
    """
    if markdown:
        # Request Markdown via query param. client.get() calls .json(), so use
        # raw httpx here to capture the plain-text response body instead.
        base = _resolve_base(url)
        try:
            r = httpx.get(
                f"{base}/mcp-skill/",
                params={"format": "markdown"},
                headers={"Accept": "text/markdown"},
                timeout=30,
            )
            raise_for_status(r)
        except RetailOpsError as e:
            handle_error(e)
            return
        except httpx.ConnectError as e:
            handle_connection_error(e, base)
            return
        sys.stdout.write(r.text)
        if not r.text.endswith("\n"):
            sys.stdout.write("\n")
        return

    # JSON mode: use the standard authenticated client so verbose logging and
    # retry logic apply. The endpoint is public so an empty/missing token is fine.
    fmt = output or state.output
    from ..client import RetailOpsClient
    prof = get_profile(state.profile)
    # Allow URL override by temporarily adjusting the profile's base_url.
    if url:
        from dataclasses import replace
        prof = replace(prof, base_url=url.rstrip("/"))
    try:
        with RetailOpsClient(prof, verbose=state.verbose) as client:
            data = client.get("mcp-skill/")
    except RetailOpsError as e:
        handle_error(e)
        return
    except httpx.ConnectError as e:
        handle_connection_error(e, prof.base_url)
        return
    render(data, fmt)
