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

run_pipx() {
  if "$PYTHON_BIN" -m pipx --version >/dev/null 2>&1; then
    "$PYTHON_BIN" -m pipx "$@"
  elif command -v pipx >/dev/null 2>&1; then
    pipx "$@"
  else
    return 127
  fi
}

apt_install() {
  if [ "$(id -u)" -eq 0 ]; then
    apt-get update
    apt-get install -y "$@"
    return 0
  fi

  if command -v sudo >/dev/null 2>&1; then
    sudo apt-get update
    sudo apt-get install -y "$@"
    return 0
  fi

  return 1
}

install_pipx() {
  echo "Installing pipx..."

  if command -v apt-get >/dev/null 2>&1; then
    if apt_install pipx; then
      return 0
    fi
  fi

  if "$PYTHON_BIN" -m pip install --user pipx; then
    return 0
  fi

  cat >&2 <<'EOF'

Could not install pipx automatically.

On Ubuntu/Debian, install it with:
  sudo apt-get update && sudo apt-get install -y pipx

Then rerun this installer.
EOF
  return 1
}

ensure_git() {
  if command -v git >/dev/null 2>&1; then
    return 0
  fi

  echo "Installing git..."
  if command -v apt-get >/dev/null 2>&1 && apt_install git; then
    return 0
  fi

  cat >&2 <<'EOF'

RetailOps CLI is installed from GitHub, so this installer needs git.

On Ubuntu/Debian, install it with:
  sudo apt-get update && sudo apt-get install -y git

Then rerun this installer.
EOF
  return 1
}

PYTHON_BIN="$(find_python || true)"
if [ -z "$PYTHON_BIN" ]; then
  echo "RetailOps CLI requires Python 3.11 or newer." >&2
  echo "Install Python 3.11+ and rerun this installer." >&2
  exit 1
fi

if ! run_pipx --version >/dev/null 2>&1; then
  install_pipx
fi

ensure_git
run_pipx ensurepath

SPEC="git+$REPO_URL"
if [ -n "$REF" ]; then
  SPEC="$SPEC@$REF"
fi

echo "Installing RetailOps CLI from $SPEC ..."
run_pipx install --force "$SPEC"

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
