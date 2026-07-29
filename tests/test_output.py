"""
tests/test_output.py
--------------------
Tests for output rendering (table / json / csv) and partial-success.

Strategy:
- Replace ``output.console`` and ``output.err_console`` with one Rich Console
  writing to a StringIO with ``force_terminal=False, no_color=True`` so we can
  assert on plain text without ANSI escape sequences.
- For JSON/CSV we validate the structured content; for table we assert on
  field tokens that should appear in the rendered text.
- Where the *stream* is the point (results on stdout, diagnostics on stderr)
  we use capsys instead, so the split is actually exercised.
"""

from __future__ import annotations

import csv
import io
import json
import sys

import pytest
import typer
from rich.console import Console

from retailops_cli import output


# ── helpers ───────────────────────────────────────────────────────────────────


@pytest.fixture
def capture_console(monkeypatch):
    """
    Replace both output consoles with one Rich console writing to a StringIO.

    Results go to stdout and diagnostics to stderr, but these tests assert on
    content rather than on stream, so merging the two keeps the assertions
    about what is rendered rather than where it landed.
    """
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
    monkeypatch.setattr(output, "err_console", fake)
    return buf


# ── JSON renderer ─────────────────────────────────────────────────────────────


# JSON goes straight to stdout when stdout is not a terminal, bypassing Rich,
# so these read capsys rather than the patched console — which also means they
# assert on exactly what a pipe would receive.


def test_render_json_emits_valid_json_for_dict(capsys):
    payload = {"id": 1, "sku": "ABC", "price": "9.99"}
    output.render(payload, fmt="json")
    assert json.loads(capsys.readouterr().out) == payload


def test_render_json_emits_valid_json_for_list(capsys):
    payload = [{"id": 1}, {"id": 2}]
    output.render(payload, fmt="json")
    assert json.loads(capsys.readouterr().out) == payload


def test_render_json_handles_paginated_envelope(capsys):
    env = {"count": 2, "next": None, "previous": None, "results": [{"id": 1}, {"id": 2}]}
    output.render(env, fmt="json")
    assert json.loads(capsys.readouterr().out) == env


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


def test_render_partial_success_json_preserves_envelope(capsys):
    """json mode emits the whole envelope to stdout; only the exit code changed."""
    env = {"succeeded": [{"id": 1}], "failed": [{"id": 2, "error": "bad"}]}
    with pytest.raises(typer.Exit) as excinfo:
        output.render_partial_success(env, fmt="json")
    assert excinfo.value.exit_code == 1
    assert json.loads(capsys.readouterr().out) == env


def test_render_partial_success_table_lists_succeeded_and_failed(capture_console):
    env = {
        "succeeded": [{"id": 1, "status": "confirmed"}, {"id": 2, "status": "confirmed"}],
        "failed":    [{"id": 99, "error": "wrong status"}],
    }
    with pytest.raises(typer.Exit) as excinfo:
        output.render_partial_success(env, fmt="table", succeeded_columns=["id", "status"])
    assert excinfo.value.exit_code == 1
    text = capture_console.getvalue()
    assert "2" in text and "succeeded" in text
    assert "1" in text and "failed" in text
    assert "99" in text
    assert "wrong status" in text


def test_render_partial_success_handles_empty_succeeded(capture_console):
    env = {"succeeded": [], "failed": [{"id": 1, "error": "x"}]}
    with pytest.raises(typer.Exit) as excinfo:
        output.render_partial_success(env, fmt="table")
    assert excinfo.value.exit_code == 1
    text = capture_console.getvalue()
    assert "No items succeeded" in text
    assert "1 failed" in text or "failed" in text


def test_json_output_stays_valid_when_a_value_is_longer_than_the_terminal(capsys):
    """
    Rich wraps to the console width and folds long strings mid-token, which
    produced invalid JSON for any notes/description field over ~80 chars.
    Piped output must be byte-exact so `--output json | jq` works.
    """
    payload = {"id": 1, "notes": "x" * 300, "url": "https://example.com/" + "y" * 200}
    output.render(payload, fmt="json")
    out = capsys.readouterr().out
    assert json.loads(out) == payload


def test_json_output_has_no_trailing_padding(capsys):
    """Rich pads every line to the console width; a pipe should get none."""
    output.render({"id": 1}, fmt="json")
    for line in capsys.readouterr().out.splitlines():
        assert line == line.rstrip(), f"trailing whitespace in {line!r}"


def test_render_partial_success_clean_batch_does_not_exit(capture_console):
    """A batch with nothing in "failed" is an ordinary success — no raise."""
    env = {"succeeded": [{"id": 1, "status": "shipped"}], "failed": []}
    output.render_partial_success(env, fmt="table", succeeded_columns=["id", "status"])
    assert "succeeded" in capture_console.getvalue()


def test_render_partial_success_sends_diagnostics_to_stderr(monkeypatch, capsys):
    """
    The counts and failure list must not pollute stdout, so that
    `orders bulk-ship --output csv > file.csv` yields a usable file.
    """
    env = {
        "succeeded": [{"id": 1, "status": "shipped"}],
        "failed":    [{"id": 9, "error": "wrong status"}],
    }
    with pytest.raises(typer.Exit):
        output.render_partial_success(env, fmt="csv", succeeded_columns=["id", "status"])
    captured = capsys.readouterr()
    assert "id,status" in captured.out
    assert "succeeded" not in captured.out
    assert "wrong status" not in captured.out
    assert "wrong status" in captured.err


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


def test_print_dry_run_with_body(capture_console, capsys):
    """Header lines go through Rich; the body takes the pipe-safe JSON path."""
    output.print_dry_run("POST", "inventory/adjust/", {"product_id": 5, "quantity": 10})
    header = capture_console.getvalue()
    assert "DRY RUN" in header
    assert "POST" in header
    assert "inventory/adjust/" in header
    assert json.loads(capsys.readouterr().out) == {"product_id": 5, "quantity": 10}


def test_print_dry_run_without_body(capture_console):
    output.print_dry_run("DELETE", "customers/9/")
    text = capture_console.getvalue()
    assert "DRY RUN" in text
    assert "DELETE" in text
    assert "customers/9/" in text
    assert "body" not in text.lower()
