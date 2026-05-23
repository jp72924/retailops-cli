# RetailOps CLI Installation

RetailOps CLI is a standalone command-line client for the RetailOps REST API. It
is distributed from GitHub first, and the recommended installer uses `pipx` so
the tool is isolated from your system Python packages.

RetailOps CLI requires Python 3.11 or newer.

## One-Command Install

macOS and Linux:

```bash
curl -fsSL https://raw.githubusercontent.com/jp72924/retailops-cli/main/install.sh | bash
```

Windows PowerShell:

```powershell
irm https://raw.githubusercontent.com/jp72924/retailops-cli/main/install.ps1 | iex
```

Verify:

```bash
retailops-cli --help
```

Log in:

```bash
retailops-cli auth login --url <RETAILOPS_API_URL>
retailops-cli auth whoami
```

## Install From A Branch Or Tag

macOS and Linux:

```bash
bash install.sh --repo https://github.com/jp72924/retailops-cli.git --ref main
```

Windows PowerShell:

```powershell
.\install.ps1 -Repo https://github.com/jp72924/retailops-cli.git -Ref main
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

Windows PowerShell:

```powershell
git clone https://github.com/jp72924/retailops-cli.git
cd retailops-cli
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
python -m pytest tests
```

## Upgrade

```bash
pipx upgrade retailops-cli
```

If the package was installed from a branch and you want to force the latest
commit:

```bash
python -m pipx install --force "git+https://github.com/jp72924/retailops-cli.git"
```

## Uninstall

```bash
pipx uninstall retailops-cli
```

## Notes

- RetailOps CLI does not install the RetailOps backend, RetailOps Kiosk,
  databases, or media storage.
- Your RetailOps administrator must provide the server API URL and your account.
- Use `retailops-cli auth config` to diagnose which profile, URL, token, and
  environment overrides are active.
