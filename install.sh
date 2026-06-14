#!/usr/bin/env bash
# Instalace akustického plašiče kun na Raspberry Pi OS (Bookworm i Bullseye).
# - nainstaluje systémovou závislost libportaudio2 (apt)
# - vytvoří venv .venv a do něj numpy + sounddevice (kvůli PEP 668 na Bookwormu)
# - nakopíruje systemd unit (NEenabluje — auto-start po bootu se nedělá)
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_NAME="acoustic-marten-deterrent.service"

echo "==> Projekt: ${PROJECT_DIR}"

# 1) Systémová závislost pro PortAudio (sounddevice).
echo "==> Instaluji libportaudio2 (apt)…"
sudo apt-get update
sudo apt-get install -y libportaudio2 python3-venv

# 2) Virtuální prostředí + Python balíčky.
echo "==> Vytvářím venv .venv…"
python3 -m venv "${PROJECT_DIR}/.venv"
"${PROJECT_DIR}/.venv/bin/pip" install --upgrade pip
echo "==> Instaluji numpy + sounddevice…"
"${PROJECT_DIR}/.venv/bin/pip" install numpy sounddevice

# 3) Config — vytvoř z příkladu, pokud ještě není.
if [ ! -f "${PROJECT_DIR}/config.ini" ]; then
  echo "==> Vytvářím config.ini z config.example.ini…"
  cp "${PROJECT_DIR}/config.example.ini" "${PROJECT_DIR}/config.ini"
fi

# 4) systemd unit — připrav s aktuálním uživatelem a cestou, nainstaluj, NEenabluj.
echo "==> Připravuji systemd unit…"
RUN_USER="${SUDO_USER:-$USER}"
TMP_UNIT="$(mktemp)"
sed \
  -e "s|^User=.*|User=${RUN_USER}|" \
  -e "s|^WorkingDirectory=.*|WorkingDirectory=${PROJECT_DIR}|" \
  -e "s|^ExecStart=.*|ExecStart=${PROJECT_DIR}/.venv/bin/python -m marten_deterrent --config ${PROJECT_DIR}/config.ini|" \
  "${PROJECT_DIR}/systemd/${SERVICE_NAME}" > "${TMP_UNIT}"
sudo cp "${TMP_UNIT}" "/etc/systemd/system/${SERVICE_NAME}"
rm -f "${TMP_UNIT}"
sudo systemctl daemon-reload

echo
echo "==> Hotovo."
echo "    Uživatel '${RUN_USER}' musí být ve skupině 'audio':  sudo usermod -aG audio ${RUN_USER}"
echo
echo "    Rychlý test zvuku:"
echo "      ${PROJECT_DIR}/.venv/bin/python -m marten_deterrent --once"
echo "      ${PROJECT_DIR}/.venv/bin/python -m marten_deterrent --list-devices"
echo
echo "    Spuštění služby (BEZ auto-startu po bootu):"
echo "      sudo systemctl start ${SERVICE_NAME}"
echo "      sudo systemctl stop  ${SERVICE_NAME}"
echo "    (Auto-start po bootu by byl 'sudo systemctl enable ${SERVICE_NAME}' — záměrně NEděláme.)"
