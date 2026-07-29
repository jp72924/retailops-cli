"""
tests/test_errors.py
--------------------
Unit tests for error-envelope parsing, human messages, and exit codes.

Coverage:
- 413 / 415 / 422 get purpose-written messages instead of the generic tail,
  and 422 keeps its `details` (the useful half of an OCR rejection).
- Timeouts read as timeouts, not as "is the server running?".
- A non-object JSON error body degrades gracefully instead of raising
  AttributeError out of raise_for_status.
- confirm_or_abort respects --yes and --dry-run.
"""

from __future__ import annotations

import httpx
import pytest
import typer

from retailops_cli import state
from retailops_cli.errors import (
    RetailOpsError,
    confirm_or_abort,
    handle_connection_error,
    raise_for_status,
)


# ── receipt-pipeline status codes ─────────────────────────────────────────────


def test_413_reports_file_size():
    e = RetailOpsError(413, "Receipt exceeds 5 MB.", "receipt_too_large")
    assert e.user_message() == "File too large: Receipt exceeds 5 MB."
    assert e.exit_code() == 1


def test_415_reports_file_type():
    e = RetailOpsError(415, "Only JPEG and PNG are accepted.", "unsupported_receipt_type")
    assert e.user_message() == "Unsupported file type: Only JPEG and PNG are accepted."


def test_422_preserves_details():
    """
    The generic fallback used to drop `details` entirely — which is where the
    OCR pipeline puts the mismatched fields.
    """
    e = RetailOpsError(
        422, "Receipt does not match the order.", "receipt_field_mismatch",
        details={"mismatches": ["amount", "paid_on"]},
    )
    msg = e.user_message()
    assert "Could not process" in msg
    assert "mismatches: amount, paid_on" in msg


def test_422_without_details_still_reads_cleanly():
    e = RetailOpsError(422, "OCR is disabled for this method.", "ocr_method_disabled")
    assert e.user_message() == "Could not process: OCR is disabled for this method."


def test_400_details_still_formatted_as_validation():
    e = RetailOpsError(
        400, "Invalid input.", "validation_error",
        details={"email": ["This field is required."]},
    )
    assert e.user_message() == "Validation failed — email: This field is required."


def test_5xx_message_names_the_actual_status():
    """It used to hardcode "HTTP 500" even for a 502 or 503."""
    assert "HTTP 503" in RetailOpsError(503, "Upstream down.", "server_error").user_message()


def test_5xx_with_a_specific_code_surfaces_the_servers_message():
    """
    A 502 from an upstream rate source carries a real explanation. The generic
    "check the server logs" branch used to swallow it.
    """
    e = RetailOpsError(502, "Rate source returned HTTP 500.", "rate_source_error")
    assert "Rate source returned HTTP 500." in e.user_message()


def test_unhandled_5xx_keeps_the_log_hint():
    """A genuine unhandled 500 has no useful message — don't pretend it does."""
    e = RetailOpsError(500, "<html>traceback</html>", "server_error")
    msg = e.user_message()
    assert "Check the RetailOps server logs" in msg
    assert "traceback" not in msg


# ── envelope parsing ──────────────────────────────────────────────────────────


def test_non_object_json_body_does_not_raise_attributeerror():
    """
    A proxy returning a bare JSON string or list on 415/502 used to escape as
    an AttributeError traceback, since only ValueError/KeyError were caught.
    """
    response = httpx.Response(502, json=["upstream", "unavailable"])
    with pytest.raises(RetailOpsError) as excinfo:
        raise_for_status(response)
    assert excinfo.value.status == 502
    assert excinfo.value.code == "http_error"


def test_non_json_body_falls_back_to_text():
    response = httpx.Response(500, text="<html>Internal Server Error</html>")
    with pytest.raises(RetailOpsError) as excinfo:
        raise_for_status(response)
    assert "Internal Server Error" in excinfo.value.error


def test_success_response_does_not_raise():
    raise_for_status(httpx.Response(200, json={"ok": True}))


# ── transport failures ────────────────────────────────────────────────────────


def test_timeout_message_differs_from_connection_refused(capsys):
    with pytest.raises(typer.Exit) as excinfo:
        handle_connection_error(httpx.ReadTimeout("timed out"), "http://x/api/v1")
    assert excinfo.value.exit_code == 2
    err = capsys.readouterr().err
    assert "Timed out" in err
    assert "Is the RetailOps server running?" not in err


def test_connection_refused_keeps_the_server_running_hint(capsys):
    with pytest.raises(typer.Exit) as excinfo:
        handle_connection_error(httpx.ConnectError("refused"), "http://x/api/v1")
    assert excinfo.value.exit_code == 2
    assert "Is the RetailOps server running?" in capsys.readouterr().err


# ── confirm_or_abort ──────────────────────────────────────────────────────────


def test_confirm_or_abort_is_skipped_by_yes(monkeypatch):
    monkeypatch.setattr(state, "yes", True)
    confirm_or_abort("Delete everything?")  # must not prompt or raise


def test_confirm_or_abort_is_skipped_by_dry_run(monkeypatch):
    """Nothing is sent under --dry-run, so there is nothing to confirm."""
    monkeypatch.setattr(state, "dry_run", True)
    confirm_or_abort("Delete everything?")


def test_confirm_or_abort_exits_130_when_declined(monkeypatch):
    monkeypatch.setattr(typer, "confirm", lambda *a, **kw: False)
    with pytest.raises(typer.Exit) as excinfo:
        confirm_or_abort("Delete everything?")
    assert excinfo.value.exit_code == 130
