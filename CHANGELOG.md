# Changelog

All notable changes to RetailOps CLI will be documented in this file.

## 0.2.0 - 2026-07-29

Closes the gap between what the RetailOps API offers and what the CLI reaches:
70 of 70 in-scope operations, up from 64 of 70.

### Breaking

- **Bulk commands now exit 1 when any item fails.** `orders bulk-confirm`,
  `orders bulk-ship`, `orders bulk-deliver`, and `inventory bulk-adjust`
  previously exited 0 no matter how many entries failed, because the API
  answers HTTP 200 either way. Partial and total failure both report exit 1;
  read the `succeeded` / `failed` arrays from `--output json` to tell them
  apart.
- **Progress and confirmation messages moved to stderr.** `✓`/`⚠`/info lines
  used to go to stdout, landing inside piped or redirected output. Results
  still go to stdout, so `--output json | jq` and `--output csv > file.csv` now
  produce clean data. Scripts that captured these messages from stdout must
  read stderr instead.

### Fixed

- **`--dry-run` is now honoured by every mutating command.** It was wired into
  8 of 45; the other 37 accepted the flag and sent the request anyway, so
  `orders delete 5 --dry-run` deleted order 5. Enforcement moved into the HTTP
  client, where no command can bypass it. Secrets are masked in the preview.
- **`--output json` no longer emits invalid JSON.** Long string values were
  wrapped mid-token at the terminal width, breaking `| jq` on any record with a
  long notes or description field.
- **Request timeouts report an error instead of a traceback**, and say they
  timed out rather than asking whether the server is running.
- **413, 415, and 422 responses keep their field-level detail**, which the
  generic error path used to discard — this is where receipt-verification
  failures explain themselves. A 5xx carrying a specific error code now shows
  its message too.
- **`--all` honours `--page-size`** instead of always requesting 100 per page,
  and the large-dataset warning fires once rather than on every page.
- **`users list --search` actually filters.** It previously returned every user
  while appearing to have searched (fixed server-side).
- **`orders bulk-confirm` now requires Manager**, matching single-order
  `confirm`. Staff could previously deduct stock through the bulk path
  (fixed server-side).
- **Deleting a category or product that is still in use returns 409**, not 500
  (fixed server-side).
- `output_format` and `page_size` in `config.toml` are now read, as documented.

### Added

- `recipient-profiles` command group (`list`, `get`, `create`, `update`,
  `delete`) — the allowlist that OCR-verified receipts are matched against. It
  previously had no CLI surface at all.
- `settings refresh-rate` to fetch the secondary exchange rate on demand.
- `settings update` gained `--recipient-validation`,
  `--secondary-rate-auto`, `--secondary-rate-source-url`, and
  `--secondary-rate-source-field`. Together with the group above, this makes
  recipient validation reachable — it could previously be neither populated nor
  switched on.
- `--version` / `-V`.

### Notes

Two API capabilities are deliberately not exposed, and are documented as such
in `PARITY.md`: the six `PUT` (full-replace) endpoints, since `PATCH` already
covers every field, and the Swagger/ReDoc HTML pages, which are browser UIs —
`schema swagger-url` and `schema redoc-url` print their addresses.

## 0.1.0 - 2026-05-23

Initial release.

- Publish RetailOps CLI as a standalone GitHub-first command-line client for the
  RetailOps REST API.
- Provide authenticated workflows for customers, catalog, inventory, orders,
  payments, settings, kiosk operations, and schema inspection.
- Add one-command installers for macOS, Linux, and Windows.
- Add Python 3.11 package metadata, MIT licensing, CI, release packaging, and
  user/security/contribution documentation.
