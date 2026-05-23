"""
tests/test_pager.py
-------------------
Tests for ``paginated_get`` and ``fetch_all`` in pager.py.

Coverage:
- paginated_get adds ``page`` and ``page_size`` to params and caps page_size at 100.
- fetch_all walks the ``next`` chain and merges results.
- fetch_all returns the synthetic envelope shape that render() can consume.
- The 500-record warning fires when --all crosses the threshold.
"""

from __future__ import annotations

import pytest

from retailops_cli.pager import fetch_all, paginated_get


BASE = "http://test.example/api/v1"


# ── paginated_get ─────────────────────────────────────────────────────────────


def test_paginated_get_adds_page_and_page_size(client, httpx_mock):
    httpx_mock.add_response(
        url=f"{BASE}/products/?page=2&page_size=10",
        json={"count": 50, "next": None, "previous": None, "results": []},
    )
    paginated_get(client, "products/", {}, page=2, page_size=10)
    qs = dict(httpx_mock.get_request().url.params)
    assert qs == {"page": "2", "page_size": "10"}


def test_paginated_get_caps_page_size_at_100(client, httpx_mock):
    httpx_mock.add_response(
        url=f"{BASE}/products/?page=1&page_size=100",
        json={"count": 0, "next": None, "previous": None, "results": []},
    )
    paginated_get(client, "products/", {}, page=1, page_size=999)
    qs = dict(httpx_mock.get_request().url.params)
    assert qs["page_size"] == "100"


def test_paginated_get_preserves_existing_params(client, httpx_mock):
    httpx_mock.add_response(
        url=f"{BASE}/products/?stock=low&page=1&page_size=25",
        json={"count": 0, "next": None, "previous": None, "results": []},
    )
    paginated_get(client, "products/", {"stock": "low"}, page=1, page_size=25)
    qs = dict(httpx_mock.get_request().url.params)
    assert qs["stock"] == "low"
    assert qs["page"]  == "1"


# ── fetch_all ─────────────────────────────────────────────────────────────────


def test_fetch_all_walks_next_chain_and_merges_results(client, httpx_mock):
    """Three pages of 2 records each merge into a single 6-record envelope."""
    httpx_mock.add_response(
        url=f"{BASE}/products/?page=1&page_size=100",
        json={
            "count": 6,
            "next":  f"{BASE}/products/?page=2&page_size=100",
            "previous": None,
            "results": [{"id": 1}, {"id": 2}],
        },
    )
    httpx_mock.add_response(
        url=f"{BASE}/products/?page=2&page_size=100",
        json={
            "count": 6,
            "next":  f"{BASE}/products/?page=3&page_size=100",
            "previous": None,
            "results": [{"id": 3}, {"id": 4}],
        },
    )
    httpx_mock.add_response(
        url=f"{BASE}/products/?page=3&page_size=100",
        json={
            "count": 6,
            "next":  None,
            "previous": None,
            "results": [{"id": 5}, {"id": 6}],
        },
    )

    merged = fetch_all(client, "products/", {})
    assert merged["count"]    == 6
    assert merged["next"]     is None
    assert merged["previous"] is None
    assert [r["id"] for r in merged["results"]] == [1, 2, 3, 4, 5, 6]
    assert len(httpx_mock.get_requests()) == 3


def test_fetch_all_single_page_does_not_loop(client, httpx_mock):
    httpx_mock.add_response(
        url=f"{BASE}/categories/?page=1&page_size=100",
        json={"count": 1, "next": None, "previous": None, "results": [{"id": 1}]},
    )
    merged = fetch_all(client, "categories/", {})
    assert merged["count"] == 1
    assert len(merged["results"]) == 1
    assert len(httpx_mock.get_requests()) == 1


def test_fetch_all_uses_page_size_100_by_default(client, httpx_mock):
    httpx_mock.add_response(
        url=f"{BASE}/products/?page=1&page_size=100",
        json={"count": 0, "next": None, "previous": None, "results": []},
    )
    fetch_all(client, "products/")
    qs = dict(httpx_mock.get_request().url.params)
    assert qs["page_size"] == "100"


def test_fetch_all_warns_above_threshold(client, httpx_mock, capsys):
    """When the merged result count crosses 500 with more pages remaining,
    print_warning should fire on stderr."""
    # Page 1: 500 results, next is page 2 (triggers warning).
    big = [{"id": i} for i in range(500)]
    httpx_mock.add_response(
        url=f"{BASE}/products/?page=1&page_size=100",
        json={
            "count": 600,
            "next":  f"{BASE}/products/?page=2&page_size=100",
            "previous": None,
            "results": big,
        },
    )
    httpx_mock.add_response(
        url=f"{BASE}/products/?page=2&page_size=100",
        json={
            "count": 600,
            "next": None,
            "previous": None,
            "results": [{"id": 600 + i} for i in range(100)],
        },
    )

    merged = fetch_all(client, "products/")
    captured = capsys.readouterr()
    # Warning is printed via Rich to stdout (output.console).
    assert "Fetching large dataset" in captured.out or "Fetching large dataset" in captured.err
    assert merged["count"] == 600
    assert len(merged["results"]) == 600
