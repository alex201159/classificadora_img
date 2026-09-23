#!/usr/bin/env bash

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
AUTOSTART_DIR="$HOME/.config/autostart"
DESKTOP_FILE="$AUTOSTART_DIR/classificadora-tampas.desktop"

if [[ ! -x "$PROJECT_DIR/.venv/bin/python" ]]; then
  printf 'Execute scripts/install_orangepi.sh antes de habilitar o inicio automatico.\n' >&2
  exit 1
fi

mkdir -p "$AUTOSTART_DIR"
cat >"$DESKTOP_FILE" <<EOF
[Desktop Entry]
Type=Application
Version=1.0
Name=Classificadora de Tampas
Comment=Interface de operacao da classificadora
Exec=$PROJECT_DIR/scripts/run_orangepi.sh
Path=$PROJECT_DIR
Terminal=false
StartupNotify=true
X-GNOME-Autostart-enabled=true
X-GNOME-Autostart-Delay=5
X-Cinnamon-Autostart-enabled=true
Categories=Utility;
EOF

chmod 644 "$DESKTOP_FILE"
printf 'Inicio automatico habilitado em %s\n' "$DESKTOP_FILE"
printf 'Para remover: rm %q\n' "$DESKTOP_FILE"
