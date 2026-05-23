"""
tests/test_output.py
--------------------
Tests for output rendering (table / json / csv) and partial-success.

Strategy:
- Replace ``output.console`` with a Rich Console that writes to a StringIO
  with ``force_terminal=False, no_color=True`` so we can assert on plain
  text without ANSI escape sequences.
- For JSON/CSV we validate the structured content; for table we assert on
  field tokens that should appear in the rendered text.
"""

from __future__ import annotations

import csv
import io
import json
import sys

import pytest
from rich.console import Console

from retailops_cli import output


# ── helpers ───────────────────────────────────────────────────────────────────


@pytest.fixture
def capture_console(monkeypatch):
    """Replace output.console with a Rich console writing to a StringIO."""
    buf = io.StringIO()
    fake = Console(
        file=buf,
        force_terminal=False,
        no_color=True,
        width=200,
        record=False,
        emoji=False,
        highlight=False,
    )
    monkeypatch.setattr(output, "console", fake)
    return buf


# ── JSON renderer ─────────────────────────────────────────────────────────────


def test_render_json_emits_valid_json_for_dict(capture_console):
    output.render({"id": 1, "sku": "ABC", "price": "9.99"}, fmt="json")
    text = capture_console.getvalue()
    # Strip Rich's ASCII frame; just look for the JSON tokens.
    assert '"id":' in text
    assert '"sku":' in text
    assert '"ABC"' in text


def test_render_json_emits_valid_json_for_list(capture_console):
    output.render([{"id": 1}, {"id": 2}], fmt="json")
    text = capture_console.getvalue()
    assert '"id":' in text
    assert "1" in text and "2" in text


def test_render_json_handles_paginated_envelope(capture_console):
    env = {"count": 2, "next": None, "previous": None, "results": [{"id": 1}, {"id": 2}]}
    output.render(env, fmt="json")
    text = capture_console.getvalue()
    assert '"count":' in text
    assert '"results":' in text


# ── CSV renderer ──────────────────────────────────────────────────────────────


def test_render_csv_for_list(capsys):
    rows = [
        {"id": 1, "sku": "A", "name": "Apple"},
        {"id": 2, "sku": "B", "name": "Banana"},
    ]
    output.render(rows, fmt="csv", columns=["id", "sku", "name"])
    captured = capsys.readouterr()
    parsed = list(csv.DictReader(io.StringIO(captured.out)))
    assert parsed == [
        {"id": "1", "sku": "A", "name": "Apple"},
        {"id": "2", "sku": "B", "name": "Banana"},
    ]


def test_render_csv_for_paginated_envelope(capsys):
    env = {
        "count": 1,
        "results": [{"id": 1, "sku": "A", "name": "Apple"}],
    }
    output.render(env, fmt="csv", columns=["id", "sku", "name"])
    parsed = list(csv.DictReader(io.StringIO(capsys.readouterr().out)))
    assert len(parsed) == 1
    assert parsed[0]["sku"] == "A"


def test_render_csv_for_single_dict_emits_one_row(capsys):
    """A single record renders as a one-row CSV."""
    output.render({"id": 7, "sku": "Z"}, fmt="csv", columns=["id", "sku"])
    parsed = list(csv.DictReader(io.StringIO(capsys.readouterr().out)))
    assert parsed == [{"id": "7", "sku": "Z"}]


def test_render_csv_flattens_nested_dict_using_human_field(capsys):
    """A nested dict (e.g. category) should render as its human-readable name."""
    rows = [{"id": 1, "category": {"id": 4, "name": "Office Supplies"}}]
    output.render(rows, fmt="csv", columns=["id", "category"])
    parsed = list(csv.DictReader(io.StringIO(capsys.readouterr().out)))
    assert parsed[0]["category"] == "Office Supplies"


# ── Table renderer ────────────────────────────────────────────────────────────


def test_render_table_paginated_envelope_includes_footer(capture_console):
    env = {
        "count": 99,
        "next":  "http://x/?page=2",
        "previous": None,
        "results": [{"id": 1, "name": "Alpha"}, {"id": 2, "name": "Beta"}],
    }
    output.render(env, fmt="table", columns=["id", "name"])
    text = capture_console.getvalue()
    # Headers and rows are present.
    assert "Id" in text
    assert "Name" in text
    assert "Alpha" in text and "Beta" in text
    # Footer surfaces the count and the more-pages hint.
    assert "Showing 2 of 99" in text
    assert "--page" in text or "--all" in text


def test_render_table_empty_list_prints_no_results(capture_console):
    output.render([], fmt="table")
    assert "No results" in capture_console.getvalue()


def test_render_table_single_record_renders_key_value(capture_console):
    output.render({"id": 5, "sku": "ABC"}, fmt="table")
    text = capture_console.getvalue()
    assert "Id" in text
    assert "Sku" in text
    assert "ABC" in text


# ── _cell formatting ──────────────────────────────────────────────────────────


def test_cell_none_renders_dash():
    assert "—" in output._cell("phone", None)


def test_cell_bool_true_yes():
    assert "Yes" in output._cell("is_active", True)


def test_cell_bool_false_no():
    assert "No" in output._cell("is_active", False)


def test_cell_status_includes_color_tag():
    """Status values pick up colour tags from _STATUS_COLORS."""
    out = output._cell("status", "paid")
    assert "green" in out
    assert "paid" in out


def test_cell_dict_returns_human_field():
    nested = {"id": 4, "name": "Office Supplies"}
    assert output._cell("category", nested) == "Office Supplies"


def test_cell_list_summarises_count():
    assert "3 items" in output._cell("items", [1, 2, 3])
    assert "1 item" in output._cell("items", [1])


# ── _infer_columns ────────────────────────────────────────────────────────────


def test_infer_columns_prefers_priority_order():
    row = {
        "description": "x",   # in _SKIP_COLS
        "id": 1,
        "name": "n",
        "extra_one": 1,
    }
    cols = output._infer_columns(row)
    # id and name come from _PRIORITY_COLS, in priority order.
    assert cols[0] == "id"
    assert "name" in cols
    # description is in _SKIP_COLS and must not be present.
    assert "description" not in cols


def test_infer_columns_drops_skip_cols():
    row = {"id": 1, "address_line1": "x", "notes": "y", "sku": "Z"}
    cols = output._infer_columns(row)
    assert "address_line1" not in cols
    assert "notes" not in cols
    assert "id" in cols
    assert "sku" in cols


# ── partial-success ───────────────────────────────────────────────────────────


def test_render_partial_success_json_preserves_envelope(capture_console):
    env = {"succeeded": [{"id": 1}], "failed": [{"id": 2, "error": "bad"}]}
    output.render_partial_success(env, fmt="json")
    text = capture_console.getvalue()
    assert '"succeeded":' in text
    assert '"failed":' in text


def test_render_partial_success_table_lists_succeeded_and_failed(capture_console):
    env = {
        "succeeded": [{"id": 1, "status": "confirmed"}, {"id": 2, "status": "confirmed"}],
        "failed":    [{"id": 99, "error": "wrong status"}],
    }
    output.render_partial_success(env, fmt="table", succeeded_columns=["id", "status"])
    text = capture_console.getvalue()
    assert "2" in text and "succeeded" in text
    assert "1" in text and "failed" in text
    assert "99" in text
    assert "wrong status" in text


def test_render_partial_success_handles_empty_succeeded(capture_console):
    env = {"succeeded": [], "failed": [{"id": 1, "error": "x"}]}
    output.render_partial_success(env, fmt="table")
    text = capture_console.getvalue()
    assert "No items succeeded" in text
    assert "1 failed" in text or "failed" in text


# ── YAML renderer (Phase 5) ───────────────────────────────────────────────────


def test_render_yaml_for_dict(capsys):
    output.render({"currency_code": "USD", "decimal_places": 2}, fmt="yaml")
    out = capsys.readouterr().out
    # Plain YAML — keys preserved in insertion order, no JSON braces.
    assert "currency_code: USD" in out
    assert "decimal_places: 2" in out
    assert "{" not in out


def test_render_yaml_for_list(capsys):
    output.render([{"id": 1}, {"id": 2}], fmt="yaml")
    out = capsys.readouterr().out
    # YAML list-of-dicts uses '-' bullets.
    assert "- id: 1" in out
    assert "- id: 2" in out


def test_render_yaml_round_trips_through_pyyaml(capsys):
    """The emitted YAML must round-trip back to the same Python value."""
    import yaml
    payload = {"a": [1, 2, {"nested": "ok"}], "b": None}
    output.render(payload, fmt="yaml")
    parsed = yaml.safe_load(capsys.readouterr().out)
    assert parsed == payload


# ── read_json_arg (Phase 5) ───────────────────────────────────────────────────


def test_read_json_arg_inline_string():
    assert output.read_json_arg('[{"id": 1}]') == [{"id": 1}]


def test_read_json_arg_from_file(workspace_tmp_path):
    f = workspace_tmp_path / "items.json"
    f.write_text('[{"product_id": 7, "quantity": 2}]', encoding="utf-8")
    parsed = output.read_json_arg(f"@{f}", what="--items")
    assert parsed == [{"product_id": 7, "quantity": 2}]


def test_read_json_arg_from_stdin(monkeypatch):
    import io as _io
    monkeypatch.setattr("sys.stdin", _io.StringIO('[{"a": 1}]'))
    assert output.read_json_arg("-") == [{"a": 1}]


def test_read_json_arg_invalid_json_exits_1(capsys):
    import typer
    with pytest.raises(typer.Exit) as excinfo:
        output.read_json_arg("not-valid-json", what="--items")
    assert excinfo.value.exit_code == 1


def test_read_json_arg_missing_file_exits_1(workspace_tmp_path, capsys):
    import typer
    missing = workspace_tmp_path / "nope.json"
    with pytest.raises(typer.Exit) as excinfo:
        output.read_json_arg(f"@{missing}", what="--adjustments")
    assert excinfo.value.exit_code == 1


# ── print_dry_run (Phase 5) ───────────────────────────────────────────────────


def test_print_dry_run_with_body(capture_console):
    output.print_dry_run("POST", "inventory/adjust/", {"product_id": 5, "quantity": 10})
    text = capture_console.getvalue()
    assert "DRY RUN" in text
    assert "POST" in text
    assert "inventory/adjust/" in text
    assert "product_id" in text
    assert "10" in text


def test_print_dry_run_without_body(capture_console):
    output.print_dry_run("DELETE", "customers/9/")
    text = capture_console.getvalue()
    assert "DRY RUN" in text
    assert "DELETE" in text
    assert "customers/9/" in text
    assert "body" not in text.lower()
