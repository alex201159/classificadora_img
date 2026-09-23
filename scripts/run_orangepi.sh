#!/usr/bin/env bash

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="$PROJECT_DIR/.venv/bin/python"

if [[ ! -x "$PYTHON" ]]; then
  printf 'Ambiente virtual ausente. Execute %s/scripts/install_orangepi.sh primeiro.\n' "$PROJECT_DIR" >&2
  exit 1
fi

if [[ -z "${DISPLAY:-}" ]]; then
  printf 'DISPLAY nao definido. Execute este comando dentro da sessao grafica do Cinnamon.\n' >&2
  exit 1
fi

export GDK_BACKEND=x11
export FLET_DESKTOP_FLAVOR=full

cd "$PROJECT_DIR"
exec "$PYTHON" main.py --flet
