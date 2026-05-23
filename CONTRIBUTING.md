# Contributing

Thanks for improving RetailOps CLI.

## Development Setup

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

## Checks

Run tests with the Python module form so the intended interpreter and package
environment are used:

```bash
python -m pytest tests
python -m build
```

Optional:

```bash
python -m coverage run --source=retailops_cli -m pytest tests
python -m coverage report -m
python -m ruff check retailops_cli tests
```

## Release

1. Update `CHANGELOG.md`.
2. Bump `version` in `pyproject.toml`.
3. Run `python -m pytest tests` and `python -m build`.
4. Commit and tag:

```bash
git tag v0.1.0
git push origin main --tags
```

The release workflow builds source and wheel distributions and uploads them to
the GitHub Release. PyPI publishing is intentionally not enabled yet.

## Installer Testing

macOS/Linux:

```bash
bash install.sh --repo https://github.com/jp72924/retailops-cli.git --ref main
```

Windows:

```powershell
.\install.ps1 -Repo https://github.com/jp72924/retailops-cli.git -Ref main
```
