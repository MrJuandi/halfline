#!/usr/bin/env bash
# Se ejecuta UNA vez en la VM (Debian/Ubuntu), con los ficheros copiados en /tmp/halfline-src (futdata/ y deploy/).
# Uso: sudo NTFY_TOPIC=<tema-largo-y-aleatorio> bash vm_setup.sh
set -euo pipefail
: "${NTFY_TOPIC:?define NTFY_TOPIC}"

apt-get update -qq && apt-get install -y -qq python3-venv rsync
id halfline &>/dev/null || useradd --system --create-home halfline
mkdir -p /opt/halfline/futdata
for f in __init__ common polymarket polymarket_live monitor; do cp "/tmp/halfline-src/futdata/$f.py" /opt/halfline/futdata/; done
python3 -m venv /opt/halfline/.venv
/opt/halfline/.venv/bin/pip install -q requests websockets psutil
mkdir -p /opt/halfline/data && chown -R halfline: /opt/halfline

echo "NTFY_TOPIC=$NTFY_TOPIC" > /etc/halfline.env && chmod 600 /etc/halfline.env
cp /tmp/halfline-src/deploy/polymarket-live.service /etc/systemd/system/
systemctl daemon-reload && systemctl enable --now polymarket-live
systemctl status polymarket-live --no-pager
