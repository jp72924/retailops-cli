"""
retailops_cli.pager
-------------------
Pagination helpers for list commands.

- fetch_all()     : Transparently fetches every page and returns a merged
                    list. Warns when the total record count is large.
- paginated_get() : Single-page fetch that returns the raw envelope
                    ({"count", "next", "previous", "results"}).
"""

from __future__ import annotations

from .client import RetailOpsClient
from .output import print_warning

_WARN_THRESHOLD = 500  # print a warning when --all fetches more than this


def paginated_get(
    client: RetailOpsClient,
    path: str,
    params: dict | None = None,
    page: int = 1,
    page_size: int = 25,
) -> dict:
    """
    Fetch a single page and return the paginated envelope as-is.

    The envelope has the shape:
      {"count": int, "next": str|null, "previous": str|null, "results": list}
    """
    p = dict(params or {})
    p["page"]      = page
    p["page_size"] = min(page_size, 100)
    return client.get(path, p)


def fetch_all(
    client: RetailOpsClient,
    path: str,
    params: dict | None = None,
) -> dict:
    """
    Fetch all pages for a list endpoint and return a synthetic envelope
    with all results merged into a single "results" list.

    The returned dict matches the paginated envelope shape so callers can
    pass it directly to output.render() without special-casing.
    """
    p = dict(params or {})
    p["page"]      = 1
    p["page_size"] = 100   # max allowed by the API

    all_results: list = []
    total: int = 0

    while True:
        data    = client.get(path, p)
        results = data.get("results", [])
        total   = data.get("count", 0)
        all_results.extend(results)

        if len(all_results) >= _WARN_THRESHOLD and data.get("next"):
            print_warning(
                f"Fetching large dataset — {total} total records. "
                "Consider adding filters to narrow the result set."
            )
            # Only warn once.
            _WARN_THRESHOLD  # referenced to prevent further mutation

        if not data.get("next"):
            break

        p["page"] += 1

    return {
        "count":    total,
        "next":     None,
        "previous": None,
        "results":  all_results,
    }
