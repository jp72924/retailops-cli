"""
retailops_cli.output
--------------------
All terminal rendering lives here.  Commands build a plain Python
dict/list and call render(); this module decides how to display it.

Supported formats (--output):
  table  — Rich table with coloured status badges (default)
  json   — Syntax-highlighted JSON, full fidelity, designed for | jq
  csv    — Plain CSV to stdout, designed for > file.csv or | awk
  yaml   — Plain YAML to stdout, designed for > file.yaml

The single render() entry point inspects the data shape:
  - Paginated envelope  {"count": N, "results": [...]} → list table + footer
  - Plain list          [...]                           → list table
  - Single object       {...}                           → key-value table

This module also hosts two cross-cutting CLI helpers:
  - read_json_arg(value)   parses a JSON-array CLI argument with optional
                           file (`@path.json`) and stdin (`-`) sources.
  - print_dry_run(...)     formats and prints a planned HTTP request when
                           the user passes `--dry-run` to a mutating command.
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.syntax import Syntax
from rich.table import Table

console     = Console()
err_console = Console(stderr=True)

# ── status badge colours ──────────────────────────────────────────────────────

_STATUS_COLORS: dict[str, str] = {
    "draft":     "dim",
    "pending":   "yellow",
    "confirmed": "blue",
    "paid":      "green",
    "shipped":   "cyan",
    "delivered": "bright_green",
    "cancelled": "red",
    "refunded":  "magenta",
}

# Column names to prefer in auto-inferred list tables (left-to-right order).
_PRIORITY_COLS = [
    "id", "order_number", "payment_number", "sku", "name",
    "full_name", "first_name", "last_name", "email",
    "customer", "status", "total_amount", "amount_outstanding",
    "amount", "unit_price", "current_stock", "quantity",
    "payment_method", "movement_type", "is_active", "created_at",
]

# Column names to hide in list tables (verbose / rarely useful in a list).
_SKIP_COLS: set[str] = {
    "description", "notes",
    "address_line1", "address_line2", "city", "state",
    "postal_code", "country",
    "updated_at", "confirmed_by", "created_by", "recorded_by",
    "tax_rate", "subtotal", "items", "subcategories",
    "status_display", "movement_type_display", "payment_method_display",
    "is_low_stock", "is_out_of_stock",
}


# ── public entry point ────────────────────────────────────────────────────────

def render(data: Any, fmt: str = "table", columns: list[str] | None = None) -> None:
    """
    Render API response data to stdout in the requested format.

    Args:
        data:    A dict, list, or paginated envelope from the API.
        fmt:     "table" | "json" | "csv" | "yaml"
        columns: Explicit list of field names for table/csv column order.
                 If None, columns are inferred automatically.
    """
    if fmt == "json":
        _render_json(data)
    elif fmt == "csv":
        _render_csv(data, columns)
    elif fmt == "yaml":
        _render_yaml(data)
    else:
        _render_table(data, columns)


# ── JSON renderer ─────────────────────────────────────────────────────────────

def _render_json(data: Any) -> None:
    text = json.dumps(data, indent=2, ensure_ascii=False)
    console.print(Syntax(text, "json", theme="monokai", word_wrap=True))


# ── YAML renderer ─────────────────────────────────────────────────────────────

def _render_yaml(data: Any) -> None:
    """Render data as YAML. Lazy-imports pyyaml so import errors are friendly."""
    try:
        import yaml
    except ImportError:
        err_console.print(
            "[red]Error:[/red] YAML output requires PyYAML. "
            "Install with: [bold]pip install pyyaml[/bold]"
        )
        raise
    text = yaml.safe_dump(data, sort_keys=False, allow_unicode=True, default_flow_style=False)
    # Strip trailing newline so Rich doesn't add a blank line of its own.
    sys.stdout.write(text)


# ── CSV renderer ──────────────────────────────────────────────────────────────

def _render_csv(data: Any, columns: list[str] | None) -> None:
    rows = _normalise_to_list(data)
    if not rows:
        return
    keys = columns or [k for k in rows[0] if k not in _SKIP_COLS]
    writer = csv.DictWriter(sys.stdout, fieldnames=keys, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({k: _flatten(row.get(k)) for k in keys})


# ── table renderer ────────────────────────────────────────────────────────────

def _render_table(data: Any, columns: list[str] | None) -> None:
    if isinstance(data, dict) and "results" in data:
        _render_list_table(data["results"], columns, meta=data)
    elif isinstance(data, list):
        _render_list_table(data, columns)
    elif isinstance(data, dict):
        _render_record_table(data)
    else:
        console.print(str(data))


def _render_list_table(
    rows: list[dict],
    columns: list[str] | None,
    meta: dict | None = None,
) -> None:
    if not rows:
        console.print("[dim]No results.[/dim]")
        if meta:
            console.print(f"[dim]Total matching: {meta.get('count', 0)}[/dim]")
        return

    keys = columns or _infer_columns(rows[0])
    tbl  = Table(
        show_header=True,
        header_style="bold",
        box=None,
        pad_edge=False,
        show_edge=False,
        expand=False,
    )
    for k in keys:
        tbl.add_column(k.replace("_", " ").title(), overflow="fold", no_wrap=False)

    for row in rows:
        tbl.add_row(*[_cell(k, row.get(k)) for k in keys])

    console.print(tbl)

    if meta:
        count    = meta.get("count", len(rows))
        showing  = len(rows)
        has_more = bool(meta.get("next"))
        footer   = f"\n[dim]Showing {showing} of {count}"
        if has_more:
            footer += " · use --page N or --all to fetch more"
        footer += "[/dim]"
        console.print(footer)


def _render_record_table(data: dict) -> None:
    tbl = Table(show_header=False, box=None, pad_edge=False, show_edge=False)
    tbl.add_column("Field", style="bold", min_width=26, no_wrap=True)
    tbl.add_column("Value")

    for k, v in data.items():
        if isinstance(v, (dict, list)):
            rendered = json.dumps(v, indent=2)
        else:
            rendered = _cell(k, v)
        tbl.add_row(k.replace("_", " ").title(), rendered)

    console.print(tbl)


# ── cell rendering ────────────────────────────────────────────────────────────

def _cell(key: str, value: Any) -> str:
    if value is None:
        return "[dim]—[/dim]"
    if isinstance(value, bool):
        return "[green]Yes[/green]" if value else "[dim]No[/dim]"
    if key == "status" and isinstance(value, str):
        color = _STATUS_COLORS.get(value.lower(), "")
        return f"[{color}]{value}[/{color}]" if color else value
    if isinstance(value, dict):
        # Return the most human-readable field from a nested object.
        for field in ("full_name", "display_name", "order_number", "name", "email", "sku"):
            if field in value:
                return str(value[field])
        return str(value)
    if isinstance(value, list):
        return f"[dim]{len(value)} item{'s' if len(value) != 1 else ''}[/dim]"
    return str(value)


def _flatten(v: Any) -> str:
    """Flatten a value to a plain string for CSV output."""
    if v is None:
        return ""
    if isinstance(v, dict):
        for field in ("full_name", "display_name", "order_number", "name", "email", "sku"):
            if field in v:
                return str(v[field])
        return json.dumps(v)
    if isinstance(v, list):
        return f"[{len(v)} items]"
    return str(v)


# ── column inference ──────────────────────────────────────────────────────────

def _infer_columns(row: dict, max_extra: int = 4) -> list[str]:
    """
    Return a column list for a list table row, ordered by _PRIORITY_COLS,
    then up to max_extra additional non-skipped fields.
    """
    available = set(row.keys())
    ordered   = [k for k in _PRIORITY_COLS if k in available]
    extras    = [k for k in row if k not in ordered and k not in _SKIP_COLS]
    return ordered + extras[:max_extra]


def _normalise_to_list(data: Any) -> list[dict]:
    if isinstance(data, dict) and "results" in data:
        return data["results"]
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return [data]
    return []


# ── convenience printers ──────────────────────────────────────────────────────

def print_success(msg: str) -> None:
    console.print(f"[green]✓[/green] {msg}")


def print_warning(msg: str) -> None:
    console.print(f"[yellow]⚠[/yellow]  {msg}")


def print_info(msg: str) -> None:
    console.print(f"[dim]{msg}[/dim]")


# ── JSON-input helper ─────────────────────────────────────────────────────────


def read_json_arg(value: str, *, what: str = "value") -> Any:
    """
    Resolve a JSON-bearing CLI argument and return the parsed object.

    Sources:
      - "@path/to/file.json" → read and parse the file's contents
      - "-"                  → read and parse stdin
      - anything else        → parse the literal string

    Raises typer.Exit(1) with a friendly stderr message on parse / IO failure.
    """
    import typer  # local import to keep this module CLI-agnostic in unit tests

    raw: str
    if value == "-":
        raw = sys.stdin.read()
    elif value.startswith("@"):
        path = Path(value[1:]).expanduser()
        try:
            raw = path.read_text(encoding="utf-8")
        except OSError as e:
            err_console.print(f"[red]Error:[/red] Cannot read {what} file [bold]{path}[/bold]: {e}")
            raise typer.Exit(1) from e
    else:
        raw = value

    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        err_console.print(
            f"[red]Error:[/red] Invalid JSON for {what}: {e.msg} (line {e.lineno}, col {e.colno})"
        )
        raise typer.Exit(1) from e


# ── --dry-run preview ─────────────────────────────────────────────────────────


def print_dry_run(method: str, path: str, body: dict | None = None) -> None:
    """
    Print a structured preview of a planned HTTP request for --dry-run.
    Goes to stdout (not stderr) so users can pipe it through jq if desired.
    """
    console.print(f"[bold yellow]DRY RUN[/bold yellow] — request was [bold]not[/bold] sent.")
    console.print(f"  [bold]{method.upper()}[/bold] {path}")
    if body is not None:
        text = json.dumps(body, indent=2, ensure_ascii=False)
        console.print("  [dim]body:[/dim]")
        console.print(Syntax(text, "json", theme="monokai", word_wrap=True))


def render_partial_success(
    data: dict,
    fmt: str,
    succeeded_columns: list[str] | None = None,
) -> None:
    """
    Render a partial-success response envelope: {"succeeded": [...], "failed": [...]}.

    In table/csv mode, succeeded rows are rendered as a list table followed by
    a plain failure list. In json mode the full envelope is rendered as-is.
    """
    if fmt == "json":
        _render_json(data)
        return

    succeeded = data.get("succeeded", [])
    failed    = data.get("failed", [])

    if succeeded:
        console.print(f"[green]✓[/green] [bold]{len(succeeded)}[/bold] succeeded:")
        render(succeeded, fmt, succeeded_columns)
    else:
        console.print("[dim]No items succeeded.[/dim]")

    if failed:
        console.print(f"\n[red]✗[/red] [bold]{len(failed)}[/bold] failed:")
        for entry in failed:
            id_part  = f"id={entry['id']}" if "id" in entry else f"product_id={entry.get('product_id', '?')}"
            console.print(f"  [dim]{id_part}[/dim]  {entry.get('error', 'unknown error')}")
