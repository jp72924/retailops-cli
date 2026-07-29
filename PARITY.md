# CLI ↔ API parity

How much of the RetailOps REST API `retailops-cli` actually reaches, and where the two
disagree.

Compiled from a full read of both repositories — every row below was checked against the
view, serializer, filter, and command source, not against either side's documentation.

**Status as of 0.2.0: closed.** All in-scope operations are reachable and all six
behavioral disparities are resolved. The audit that produced this document is preserved
below, with each finding marked and dated, because the reasoning is worth keeping even
though the defects are gone.

| | Audit (0.1.0) | Now (0.2.0) |
|---|---|---|
| API operations | 78 | 78 |
| Deliberate non-goals | — | 8 |
| In-scope operations | 70 | 70 |
| Reachable | **64 (91%)** | **70 (100%)** |
| CLI commands | 71 | 78 |
| Behavioral disparities | 6 | **0** |

**Counting rule:** one HTTP operation per row. A command counts as reaching an operation
only if it actually issues that request.

Status column: **Yes** = reachable · **Caveat** = reachable, with the note applying ·
**—** = no command issues this request.

---

## Deliberate non-goals

Eight of the 78 operations are intentionally not exposed. These are decisions, not gaps.

| Operations | Why |
|---|---|
| `PUT` on users, customers, categories, products, orders, recipient profiles (6) | `PATCH` already covers every writable field. For orders it is doubly redundant — `PATCH` replaces all line items wholesale. A full-replace command would differ from `update` only in ways users would trip on. `client.put()` remains implemented and tested against the day this changes. |
| `GET /schema/swagger/`, `GET /schema/redoc/` (2) | Browser HTML, not machine-readable. `schema swagger-url` and `schema redoc-url` print the addresses; `schema get` fetches the OpenAPI document itself. |

---

## Auth — 5/5

| Capability | API | CLI | Reachable |
|---|---|---|---|
| Obtain a token | `POST auth/token/` | `auth login` | Yes |
| Revoke a token | `POST auth/token/revoke/` | `auth logout` | Yes |
| Read the current identity | `GET auth/me/` | `auth whoami` | Yes |
| Request a password reset | `POST auth/password-reset/` | `auth passwd-reset` | Yes |
| Confirm a password reset | `POST auth/password-reset/confirm/` | `auth passwd-reset-confirm` | Yes |

- All three public endpoints go through `client.post_anon()` as of 0.2.0; they previously
  used raw `httpx.post`, skipping error-envelope parsing, verbose logging, and 429 retry.
- `auth logout` clears the local token even when the server is unreachable.
- Confirming a reset drops every token for that user server-side, forcing a re-login.

## Dashboard — 1/1

| Capability | API | CLI | Reachable |
|---|---|---|---|
| Month-to-date stats and 5 recent orders | `GET dashboard/` | `dashboard` | Yes |

Renders a bespoke summary panel rather than the generic table.

## Roles — 2/2

| Capability | API | CLI | Reachable |
|---|---|---|---|
| List roles | `GET roles/` | `roles list` | Caveat |
| Get a role | `GET roles/{id}/` | `roles get` | Yes |

- `roles list` sends no `page` or `page_size`, so it shows only the first 25 of a paginated
  response. Latent rather than live — only four roles are seeded.

## Users & staff — 7/7

| Capability | API | CLI | Reachable |
|---|---|---|---|
| List users | `GET users/` | `users list` | Yes |
| Create a user | `POST users/` | `users create` | Yes |
| Get a user | `GET users/{id}/` | `users get` | Yes |
| Replace a user | `PUT users/{id}/` | — | *non-goal* |
| Update a user | `PATCH users/{id}/` | `users update` | Caveat |
| Change a password | `POST users/{id}/change-password/` | `users passwd` | Yes |
| Deactivate | `POST users/{id}/deactivate/` | `users deactivate` | Yes |
| Reactivate | `POST users/{id}/reactivate/` | `users reactivate` | Yes |

- `users list --search` matches email and both name fields as of 0.2.0 — see finding 2.
- `users update` cannot toggle `is_active`; only deactivate/reactivate can.
- `users get` on another user's record is refused for non-admins.
- `users passwd` is an admin override — the old password is not required.
- `users reactivate` is the only mutating command with neither a prompt nor dry-run.

## Customers — 5/5

| Capability | API | CLI | Reachable |
|---|---|---|---|
| List & search | `GET customers/` | `customers list` | Yes |
| Create | `POST customers/` | `customers create` | Yes |
| Get | `GET customers/{id}/` | `customers get` | Yes |
| Replace | `PUT customers/{id}/` | — | *non-goal* |
| Update | `PATCH customers/{id}/` | `customers update` | Yes |
| Delete, blocked when orders exist | `DELETE customers/{id}/` | `customers delete` | Yes |

- Search covers name and email only. That is a server-side limit the back-office UI and MCP
  share — not a CLI gap.
- All 14 writable fields are exposed on create, including the link to a user account.
- This is the one delete guard that is really implemented (a 409), and the CLI names it properly.

## Categories — 5/5

| Capability | API | CLI | Reachable |
|---|---|---|---|
| List & search | `GET categories/` | `categories list` | Yes |
| Create | `POST categories/` | `categories create` | Yes |
| Get | `GET categories/{id}/` | `categories get` | Yes |
| Replace | `PUT categories/{id}/` | — | *non-goal* |
| Update | `PATCH categories/{id}/` | `categories update` | Yes |
| Delete | `DELETE categories/{id}/` | `categories delete` | Yes |

- Deleting a category that still has products returns 409 as of 0.2.0; it previously 500'd,
  because the guard the docstring promised was never written.

## Products — 6/6

| Capability | API | CLI | Reachable |
|---|---|---|---|
| List with catalog filters | `GET products/` | `products list` | Yes |
| Create, with image upload | `POST products/` | `products create` | Yes |
| Get | `GET products/{id}/` | `products get` | Yes |
| Replace | `PUT products/{id}/` | — | *non-goal* |
| Update, replace or clear the image | `PATCH products/{id}/` | `products update` | Yes |
| Delete | `DELETE products/{id}/` | `products delete` | Yes |
| Movement history | `GET products/{id}/movements/` | `products movements` | Yes |

- `--category`, `--stock`, `--unit`, `--active` map one-to-one onto the server filter set.
- Create and update switch to multipart when `--image` is given.
- Deleting a product referenced by orders or stock movements returns 409 as of 0.2.0.
- Neither side filters movement history — exact parity.

## Inventory movements — 4/4

| Capability | API | CLI | Reachable |
|---|---|---|---|
| List & filter across all products | `GET inventory/` | `inventory list` | Yes |
| Get a movement | `GET inventory/{id}/` | `inventory get` | Yes |
| Manual adjustment | `POST inventory/adjust/` | `inventory adjust` | Yes |
| Bulk adjustment | `POST inventory/bulk-adjust/` | `inventory bulk-adjust` | Yes |

- All five filters match the server filter set exactly.
- `inventory adjust` is the only command whose confirmation prompt defaults to yes.
- `inventory bulk-adjust` validates the payload client-side before sending.

## Sales orders — 12/12

| Capability | API | CLI | Reachable |
|---|---|---|---|
| List, search, filter | `GET orders/` | `orders list` | Yes |
| Create a draft | `POST orders/` | `orders create` | Yes |
| Get | `GET orders/{id}/` | `orders get` | Yes |
| Replace | `PUT orders/{id}/` | — | *non-goal* |
| Edit a draft | `PATCH orders/{id}/` | `orders update` | Yes |
| Delete a draft | `DELETE orders/{id}/` | `orders delete` | Yes |
| Submit → Confirm → Ship → Deliver | `POST orders/{id}/submit\|confirm\|ship\|deliver/` | `orders submit` / `confirm` / `ship` / `deliver` | Yes |
| Cancel | `POST orders/{id}/cancel/` | `orders cancel` | Yes |
| Refund | `POST orders/{id}/refund/` | `orders refund` | Yes |
| Bulk confirm / ship / deliver | `POST orders/bulk-transition/` | `orders bulk-confirm` / `bulk-ship` / `bulk-deliver` | Yes |

- The transitions row stands for 4 operations; the bulk row covers all 3 server-side actions.
- Missing `PUT` is moot — `PATCH` already replaces every line item.
- Editing and deleting are Draft-only, enforced server-side with a 409.
- `orders confirm` deducts stock with no prompt and no dry-run. `orders delete` prompts but
  ignores `--dry-run`.
- `orders refund` is the only command that makes you retype the ID.
- Order search is limited to `order_number` server-side.
- See finding 5 — the bulk path skips the role gate the single path enforces.

## Payments — 5/5

| Capability | API | CLI | Reachable |
|---|---|---|---|
| List & filter | `GET payments/` | `payments list` | Yes |
| Record a payment | `POST payments/` | `payments record` | Yes |
| Get | `GET payments/{id}/` | `payments get` | Yes |
| Verify a receipt through OCR | `POST payments/receipts/verify/` | `payments verify-receipt` | Yes |
| OCR provider health | `GET payments/receipts/healthz/` | `payments receipt-healthz` | Yes |

- All eight filters are exposed, including four the API guide never documents
  (`method`, `status`, `has_receipt`, `bank`).
- Every OCR field is exposed on record: transaction key, receipt image, OCR payload.
- Payments are immutable once created — no update path exists on any surface, by design.
- `verify-receipt` requires an order or an expected amount; the CLI checks that first.

## Recipient profiles — 5/5

| Capability | API | CLI | Reachable |
|---|---|---|---|
| List, search & filter | `GET payment-recipient-profiles/` | `recipient-profiles list` | Yes |
| Create | `POST payment-recipient-profiles/` | `recipient-profiles create` | Yes |
| Get | `GET payment-recipient-profiles/{id}/` | `recipient-profiles get` | Yes |
| Replace | `PUT payment-recipient-profiles/{id}/` | — | *non-goal* |
| Update | `PATCH payment-recipient-profiles/{id}/` | `recipient-profiles update` | Yes |
| Delete | `DELETE payment-recipient-profiles/{id}/` | `recipient-profiles delete` | Yes |

This is the allowlist receipt verification matches against. Manager+ for every operation,
including list and get — these carry bank-account and document identifiers.

- `--method` and `--active` filter server-side; `filterset_fields` was added to the
  viewset in 0.2.0, without which those flags would have been silently inert.
- `--inactive` on update takes a profile out of matching without losing the record.

## Settings — 3/3

| Capability | API | CLI | Reachable |
|---|---|---|---|
| Read currency & OCR configuration | `GET settings/` | `settings get` | Yes |
| Update configuration | `PATCH settings/` | `settings update` | Yes |
| Refresh the exchange rate | `POST settings/secondary-rate/refresh/` | `settings refresh-rate` | Yes |

- `settings update` covers all 23 writable fields.
- `--secondary-rate` sets the rate by hand; `settings refresh-rate` fetches it from the
  configured source. MCP still lacks the refresh endpoint.
- `--recipient-validation` is refused by the server until an active recipient profile
  exists, so it is only usable alongside the group above — which is what made this a
  two-sided gap rather than a missing flag.
- The OCR API key always reads back masked.

## Schema & discovery — 2/2

| Capability | API | CLI | Reachable |
|---|---|---|---|
| OpenAPI schema | `GET schema/` | `schema get` | Yes |
| Swagger UI | `GET schema/swagger/` | `schema swagger-url` | *non-goal* |
| ReDoc UI | `GET schema/redoc/` | `schema redoc-url` | *non-goal* |
| MCP skill card | `GET mcp-skill/` | `mcp-skill` | Yes |

- The two UI commands print a URL; no request is made.
- `schema get` writes YAML or JSON straight to stdout.
- The MCP skill card endpoint is public and needs no token.

## Kiosk — 8/8

| Capability | API | CLI | Reachable |
|---|---|---|---|
| Identify a customer by ID number | `POST kiosk/identify/` | `kiosk identify` | Yes |
| Register a walk-in customer | `POST kiosk/register/` | `kiosk register` | Yes |
| Search products | `GET kiosk/products/` | `kiosk products` | Yes |
| Get a product by ID | `GET kiosk/products/{id}/` | `kiosk product-get` | Yes |
| Look up a product by SKU | `GET kiosk/product/{sku}/` | `kiosk product-lookup` | Yes |
| Checkout | `POST kiosk/checkout/` | `kiosk checkout` | Yes |
| Fetch a receipt | `GET kiosk/receipt/{order_id}/` | `kiosk receipt` | Yes |
| Heartbeat | `POST kiosk/heartbeat/` | `kiosk heartbeat` | Yes |

- Separate `KioskKey` auth scheme, which the CLI models correctly.
- `kiosk register` requires all nine fields and none of them prompt.
- Product search caps at 6 results server-side and never paginates, so the absent page flags
  are correct rather than a gap.
- Checkout is one atomic server transaction: order, stock, payment, delivery.
- Receipt fetch is scoped to the station's own orders.

---

## What the CLI adds that the API has no equivalent for

Coverage runs both ways. Five commands make no HTTP call at all, and several cross-cutting
behaviors exist only on the client.

| | |
|---|---|
| `auth config` / `profiles` / `use` | Multi-profile management, entirely local. Resolution runs flag → environment → config file → default. |
| `--output json` / `csv` / `yaml` | Four renderers over one response shape. Verbose HTTP logging goes to stderr so a JSON pipe stays clean. |
| `--all` | Walks the `next` chain automatically and warns past 500 rows. The API only ever returns one page. |
| Client-side validation | Zero-quantity adjustments, unknown payment methods, and malformed bulk payloads are rejected before any request goes out. |
| 429 retry | Up to three retries honoring `Retry-After`, against eleven distinct server throttle scopes. |
| Confirmation prompts | Seven destructive commands prompt; `orders refund` makes you retype the ID. The API has no such concept. |

---

## Where the CLI and the server disagreed

All six are resolved in 0.2.0. The findings are kept as written at audit time — each is
followed by a note on how it was closed, so the reasoning survives alongside the fix.

### 1. `--dry-run` is honored by 8 of 45 mutating commands — data loss

The other 37 accept the flag and send the request anyway, including `orders delete`,
`products delete`, `categories delete`, all four single-order transitions, and every
`bulk-*`. So this deletes order 5:

```bash
retailops-cli orders delete 5 --dry-run
```

Wired correctly: `orders cancel`, `orders refund`, `customers delete`, `users deactivate`,
`inventory adjust`, `inventory bulk-adjust`, `payments record`, `kiosk checkout`.

`USER_GUIDE.md:1486` names the delete commands as covered; only `customers delete` is.

> **Resolved in 0.2.0.** Enforcement moved into `client._send`, the single choke point every
> mutating request already passed through, replacing 26 hand-copied blocks. `GET` is exempt.
> Confirmation prompts moved to a shared `confirm_or_abort` so the two cannot drift apart
> again — that drift is what produced the bug. Secrets are masked in the preview, which
> centralising made necessary: the preview now renders the real wire payload.

### 2. `users list --search` returns everyone — silent wrong result

The CLI sends `?search=`, but `UserViewSet` declares no `search_fields`, so DRF's
`SearchFilter` passes the queryset through untouched. The result looks filtered and never
was.

`--ordering` on the same command *does* work, through DRF's serializer-field fallback. Two
adjacent flags, opposite behavior, and nothing in `--help` says so.

> **Resolved in 0.2.0**, server-side: `search_fields = ['email', 'first_name', 'last_name']`
> on `UserViewSet`. Fixing it at the source was the only honest option — the alternative was
> removing a flag people reasonably expect to exist.

### 3. Recipient validation is unreachable in both directions — feature walled off

No command touches `/payment-recipient-profiles/`, **and** `settings update` omits
`recipient_validation_enabled` — which the API refuses to enable unless at least one active
profile already exists. The allowlist that receipt verification matches against can be
neither populated nor switched on from the CLI.

> **Resolved in 0.2.0.** Both halves had to land together, which is what made this the most
> interesting of the six: the `recipient-profiles` group plus `--recipient-validation` on
> `settings update`. Verified in sequence — enabling validation is refused with no profiles,
> and succeeds once one exists.

### 4. Bulk partial failure always exits 0 — scripting hazard

`render_partial_success` prints the failed rows but sets no exit code, and the API returns
`200` even when every item fails. A 50-row `bulk-adjust` in which all 50 error is
indistinguishable from total success to the calling shell.

> **Resolved in 0.2.0**, breaking. Exit 1 whenever `failed` is non-empty, partial and total
> alike. A distinct code for total failure was considered and rejected: it invites
> `if [ $? -eq 1 ]` scripts that miss the worse case. Use the `succeeded`/`failed` arrays
> from `--output json` to tell them apart.

### 5. The bulk path skips the role gate the single path enforces — inherited from the API

`orders confirm` requires Manager or Admin. `orders bulk-confirm` resolves to
Staff-or-above, because `OrderViewSet.get_permissions()` is overridden and never reads the
action's own `permission_classes`. Same stock deduction, two different authorizations, and
the CLI presents both identically.

This is a server bug the CLI merely exposes — but the CLI is what makes it easy to reach.

> **Resolved in 0.2.0**, server-side: `bulk_transition` added to the Manager+ branch of
> `get_permissions()`. The `@action(permission_classes=[...])` on the decorator was dead
> code, since the override never consulted it; a comment at the override now says so.

### 6. A request timeout produces a traceback — unhandled error

Every command catches `httpx.ConnectError` and nothing else. The client's own docstring
tells callers to catch `httpx.TimeoutException`, and none do. `payments verify-receipt` — a
synchronous OCR round-trip against a 30-second default client timeout — is the likeliest
command to hit it and the only one with no graceful exit.

> **Resolved in 0.2.0.** All 60 `except httpx.ConnectError` clauses widened to
> `httpx.RequestError`, the shared parent of both, and `handle_connection_error` now says a
> request timed out rather than asking whether the server is running.

### Smaller notes

All resolved in 0.2.0 except where noted.

- ~~`--all` ignores `--page-size`; the pager hardcodes 100 per request.~~ An explicit
  `--page-size` now wins; the built-in default of 25 still does not, so `--all` keeps
  fetching 100 per round-trip unless asked otherwise.
- ~~The 500-row warning re-fires on every page — the guard meant to suppress it is a bare
  expression statement, not an assignment.~~ Latches on a local flag.
- ~~OCR's `413`, `415`, and `422` codes fall through to the generic error branch and exit 1
  with a raw message.~~ Each has its own branch, and `422` keeps its `details`. A `5xx`
  carrying a specific code now surfaces its message too.
- ~~`client.put()` and `files.multipart_files()` are implemented and never called.~~
  `multipart_files` deleted. `client.put()` kept deliberately — see *Deliberate non-goals*.
- ~~The config file documents `output_format` and `page_size` keys that nothing reads.~~
  Both are now read, with an explicit flag taking precedence.
- ~~There is no `--version` flag, though `__version__` is defined.~~ Added, as `--version` / `-V`.

### Found while fixing, not during the audit

- **`--output json` emitted invalid JSON.** Rich wraps to the console width, and when stdout
  is not a terminal that width falls back to 80 — folding any string value longer than the
  line by inserting a newline *inside* the quoted token. `| jq` failed on any record with a
  long notes or description field. Piped output now bypasses Rich, as the YAML and CSV
  renderers always did.
- **`raise_for_status` raised `AttributeError` on a non-object JSON body.** A proxy
  answering `415` or `502` with a bare list or string escaped as a traceback; only
  `ValueError`/`KeyError` were caught.
- **A `5xx` with a real error envelope had its message discarded.** Surfaced only after the
  server-side envelope fix landed — neither change was wrong alone.

---

## Documentation discrepancies found while compiling this

All six corrected in 0.2.0. Two of them the code caught up with instead:

1. ~~`USER_GUIDE.md:1486` claims `--dry-run` covers the delete commands. Only `customers
   delete` is wired.~~ The claim is now true — see finding 1.
2. ~~`USER_GUIDE.md:373` lists six dry-run commands and omits `payments record` and
   `kiosk checkout`, both of which are wired.~~ The list is gone; `--dry-run` covers
   everything that mutates.
3. ~~`USER_GUIDE.md:321` shows a pagination footer format that does not match what the
   renderer emits.~~ Corrected against real output.
4. ~~`USER_GUIDE.md:312` shows a `Total: 2` footer; no such string exists.~~ Corrected.
5. ~~`USER_GUIDE.md:304` lists `customers list` columns that do not match the actual set.~~
   Corrected.
6. ~~`USER_GUIDE.md:343` says creating asks for confirmation. No `create` command ever
   confirms.~~ Reworded to name what actually prompts, and why refund differs.

---

## Method

Both repositories were read in full — views, serializers, filters, permissions, and every
command module — rather than trusting either side's documentation, which is how the six
discrepancies above surfaced.

Each finding was pinned by a test written to fail against the unfixed code before the fix
landed. For the server-side findings this was checked explicitly: with the fixes stashed,
all nine new API tests failed and three more errored with 500s.
