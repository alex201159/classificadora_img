#!/usr/bin/env bash

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="$PROJECT_DIR/.venv"

if [[ "$(uname -m)" != "aarch64" && "$(uname -m)" != "arm64" ]]; then
  printf 'Aviso: arquitetura detectada: %s (esperado: aarch64).\n' "$(uname -m)"
fi

if ! command -v sudo >/dev/null 2>&1; then
  printf 'Erro: o comando sudo nao esta disponivel.\n' >&2
  exit 1
fi

printf 'Instalando dependencias do Debian para camera e interface...\n'
sudo apt update
sudo apt install -y \
  ca-certificates \
  git \
  libgdk-pixbuf-2.0-0 \
  libgbm1 \
  libnss3 \
  libsecret-1-0 \
  libx11-6 \
  libxcomposite1 \
  libxdamage1 \
  libxrandr2 \
  python3 \
  python3-numpy \
  python3-opencv \
  python3-pip \
  python3-venv \
  python3-yaml \
  v4l-utils

install_apt_variant() {
  local package
  for package in "$@"; do
    if apt-cache show "$package" >/dev/null 2>&1; then
      sudo apt install -y "$package"
      return 0
    fi
  done
  printf 'Erro: nenhum destes pacotes foi encontrado: %s\n' "$*" >&2
  return 1
}

# Debian 13 usa nomes t64 em algumas bibliotecas; as alternativas mantem o
# instalador utilizavel tambem em imagens Armbian que preservam o nome antigo.
install_apt_variant libgtk-3-0t64 libgtk-3-0
install_apt_variant libglib2.0-0t64 libglib2.0-0
install_apt_variant libasound2t64 libasound2

printf 'Criando ambiente Python em %s...\n' "$VENV_DIR"
python3 -m venv --system-site-packages "$VENV_DIR"
"$VENV_DIR/bin/python" -m pip install --upgrade pip
"$VENV_DIR/bin/python" -m pip install 'flet>=1.0,<2' 'pytest>=7.0'

if getent group video >/dev/null 2>&1; then
  sudo usermod -aG video "$USER"
fi
if getent group gpio >/dev/null 2>&1; then
  sudo usermod -aG gpio "$USER"
fi

printf 'Validando dependencias Python...\n'
"$VENV_DIR/bin/python" -c 'import cv2, flet, numpy, yaml; print("OpenCV", cv2.__version__); print("Flet", flet.__version__)'
"$VENV_DIR/bin/python" -m pytest -q "$PROJECT_DIR/tests"

cat <<EOF

Instalacao concluida.

1. Encerre a sessao e entre novamente para aplicar o grupo video.
2. Conecte a camera e execute:
   $PROJECT_DIR/scripts/check_orangepi.sh
3. Inicie a interface com:
   $PROJECT_DIR/scripts/run_orangepi.sh

O GPIO real continua bloqueado enquanto machine.simulation estiver true.
EOF
