#!/usr/bin/env bash

set -u

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="$PROJECT_DIR/.venv/bin/python"
errors=0

printf '%-24s %s\n' 'Arquitetura:' "$(uname -m)"
printf '%-24s %s\n' 'Kernel:' "$(uname -r)"
printf '%-24s %s\n' 'Sessao grafica:' "${XDG_SESSION_TYPE:-nao informada}"
printf '%-24s %s\n' 'Display:' "${DISPLAY:-nao informado}"
printf '%-24s %s\n' 'Usuario:' "$USER"
printf '%-24s %s\n' 'Grupos:' "$(id -nG)"

if [[ ! -x "$PYTHON" ]]; then
  printf '\n[ERRO] Ambiente virtual ausente. Execute scripts/install_orangepi.sh.\n'
  exit 1
fi

printf '\nCameras V4L2:\n'
if command -v v4l2-ctl >/dev/null 2>&1; then
  v4l2-ctl --list-devices || true
else
  printf '[ERRO] v4l2-ctl nao instalado.\n'
  errors=$((errors + 1))
fi

printf '\nDeteccao pelo aplicativo:\n'
if ! (cd "$PROJECT_DIR" && "$PYTHON" main.py --detect-cameras); then
  errors=$((errors + 1))
fi

printf '\nBackend wiringOP:\n'
if command -v gpio >/dev/null 2>&1; then
  gpio -v || true
  printf 'Execute "gpio readall" para conferir a pinagem da placa.\n'
else
  printf '[AVISO] comando gpio ausente; mantenha o modo simulacao.\n'
fi

if (cd "$PROJECT_DIR" && "$PYTHON" -c 'from hardware.gpio import OrangePiGPIO; gpio = OrangePiGPIO(); gpio.close()') >/dev/null 2>&1; then
  printf 'Backend Python do wiringOP inicializado.\n'
else
  printf '[AVISO] backend Python do wiringOP indisponivel; mantenha a simulacao.\n'
fi

printf '\nConfiguracao de seguranca:\n'
if grep -Eq '^  simulation: true([[:space:]]|$)' "$PROJECT_DIR/config/machine.yaml"; then
  printf 'OK - simulacao ativa.\n'
else
  printf '[AVISO] simulacao nao esta ativa. Confirme a interface eletrica antes de iniciar.\n'
fi

exit "$errors"
