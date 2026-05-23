#!/usr/bin/env bash
set -euo pipefail

REPO_URL="https://github.com/jp72924/retailops-cli.git"
REF=""
INSTALL_COMPLETION=1

usage() {
  cat <<'EOF'
RetailOps CLI installer

Usage:
  install.sh [--repo URL] [--ref BRANCH_OR_TAG] [--no-completion]

Examples:
  curl -fsSL https://raw.githubusercontent.com/jp72924/retailops-cli/main/install.sh | bash
  bash install.sh --repo https://github.com/jp72924/retailops-cli.git --ref main
EOF
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --repo)
      REPO_URL="${2:-}"
      shift 2
      ;;
    --ref)
      REF="${2:-}"
      shift 2
      ;;
    --no-completion)
      INSTALL_COMPLETION=0
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

find_python() {
  for cmd in python3 python; do
    if command -v "$cmd" >/dev/null 2>&1; then
      if "$cmd" - <<'PY'
import sys
raise SystemExit(0 if sys.version_info >= (3, 11) else 1)
PY
      then
        echo "$cmd"
        return 0
      fi
    fi
  done
  return 1
}

PYTHON_BIN="$(find_python || true)"
if [ -z "$PYTHON_BIN" ]; then
  echo "RetailOps CLI requires Python 3.11 or newer." >&2
  echo "Install Python 3.11+ and rerun this installer." >&2
  exit 1
fi

if ! "$PYTHON_BIN" -m pipx --version >/dev/null 2>&1; then
  echo "Installing pipx..."
  "$PYTHON_BIN" -m pip install --user pipx
fi

"$PYTHON_BIN" -m pipx ensurepath

SPEC="git+$REPO_URL"
if [ -n "$REF" ]; then
  SPEC="$SPEC@$REF"
fi

echo "Installing RetailOps CLI from $SPEC ..."
"$PYTHON_BIN" -m pipx install --force "$SPEC"

if [ "$INSTALL_COMPLETION" -eq 1 ] && command -v retailops-cli >/dev/null 2>&1; then
  retailops-cli --install-completion || true
fi

cat <<'EOF'

RetailOps CLI is installed.

Next:
  retailops-cli --help
  retailops-cli auth login --url <RETAILOPS_API_URL>
  retailops-cli auth whoami

If the command is not found, restart your terminal or run:
  python -m pipx ensurepath
EOF
