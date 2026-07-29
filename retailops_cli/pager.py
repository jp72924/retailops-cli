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

from . import state
from .client import RetailOpsClient
from .output import print_warning

_WARN_THRESHOLD = 500  # print a warning when --all fetches more than this
_ALL_PAGE_SIZE  = 100  # API maximum; --all wants the fewest round-trips


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
    page_size: int | None = None,
) -> dict:
    """
    Fetch all pages for a list endpoint and return a synthetic envelope
    with all results merged into a single "results" list.

    The returned dict matches the paginated envelope shape so callers can
    pass it directly to output.render() without special-casing.

    Requests 100 records per round-trip by default — the API maximum — since
    --all is about fetching everything in as few calls as possible. An explicit
    --page-size overrides that; the global 25 default does not.
    """
    if page_size is None:
        page_size = state.page_size if state.page_size_explicit else _ALL_PAGE_SIZE

    p = dict(params or {})
    p["page"]      = 1
    p["page_size"] = min(page_size, 100)

    all_results: list = []
    total: int = 0
    warned = False

    while True:
        data    = client.get(path, p)
        results = data.get("results", [])
        total   = data.get("count", 0)
        all_results.extend(results)

        if not warned and len(all_results) >= _WARN_THRESHOLD and data.get("next"):
            print_warning(
                f"Fetching large dataset — {total} total records. "
                "Consider adding filters to narrow the result set."
            )
            warned = True

        if not data.get("next"):
            break

        p["page"] += 1

    return {
        "count":    total,
        "next":     None,
        "previous": None,
        "results":  all_results,
    }
