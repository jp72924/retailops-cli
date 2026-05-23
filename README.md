# RetailOps CLI

[![CI](https://github.com/jp72924/retailops-cli/actions/workflows/ci.yml/badge.svg)](https://github.com/jp72924/retailops-cli/actions/workflows/ci.yml)

RetailOps CLI is a standalone command-line client for the RetailOps REST API. It
gives operators and developers a terminal-first way to run authenticated
workflows for customers, catalog, inventory, orders, payments, settings, kiosk
operations, and API schema inspection.

The CLI does not install or run the RetailOps backend, RetailOps Kiosk, a
database, or object storage. It connects to an existing RetailOps API at
`/api/v1/`.

## Install

macOS and Linux:

```bash
curl -fsSL https://raw.githubusercontent.com/jp72924/retailops-cli/main/install.sh | bash
```

Windows PowerShell:

```powershell
irm https://raw.githubusercontent.com/jp72924/retailops-cli/main/install.ps1 | iex
```

The installer requires Python 3.11 or newer and installs the CLI with `pipx`
from GitHub.

## First Run

Log in to a RetailOps server:

```bash
retailops-cli auth login --url http://127.0.0.1:8000/api/v1
retailops-cli auth whoami
retailops-cli auth config
```

Then try a read-only command:

```bash
retailops-cli dashboard
retailops-cli products list --stock low
retailops-cli orders list --page-size 10
```

## Common Commands

```bash
retailops-cli --help
retailops-cli auth login --url <RETAILOPS_API_URL>
retailops-cli customers list
retailops-cli products list --search shoes
retailops-cli inventory adjust --product-id 5 --quantity 10 --notes "Restock"
retailops-cli orders create --customer-id 12 --items '[{"product_id":5,"quantity":2}]'
retailops-cli payments record --order 88 --amount 19.99 --method cash
retailops-cli settings get --output yaml
```

Use `--dry-run` on supported mutating commands to preview the HTTP request before
the CLI calls the API:

```bash
retailops-cli --dry-run inventory adjust --product-id 5 --quantity 10
```

## Manual Developer Install

```bash
git clone https://github.com/jp72924/retailops-cli.git
cd retailops-cli
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
python -m pytest tests
```

On Windows PowerShell:

```powershell
git clone https://github.com/jp72924/retailops-cli.git
cd retailops-cli
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
python -m pytest tests
```

## Configuration

The CLI stores profiles locally:

- Windows: `%APPDATA%\retailops\config.toml`
- macOS/Linux: `~/.config/retailops/config.toml`

Environment variables can override config for one run:

- `RETAILOPS_PROFILE`
- `RETAILOPS_BASE_URL`
- `RETAILOPS_TOKEN`
- `RETAILOPS_KIOSK_API_KEY`

Run this when something points at the wrong server or token:

```bash
retailops-cli auth config
```

## Upgrade And Uninstall

Upgrade from GitHub:

```bash
pipx upgrade retailops-cli
```

Uninstall:

```bash
pipx uninstall retailops-cli
```

## Troubleshooting

- `retailops-cli: command not found`: restart the terminal, then run
  `python -m pipx ensurepath`.
- Python is too old: install Python 3.11 or newer and rerun the installer.
- 401 Unauthorized: run `retailops-cli auth login --url <RETAILOPS_API_URL>`.
- 403 Permission denied: your RetailOps user role does not allow that action.
- Wrong server or token: run `retailops-cli auth config` and check the source of
  each value.

See `USER_GUIDE.md` for the full user manual and `INSTALL.md` for detailed
installation paths.
