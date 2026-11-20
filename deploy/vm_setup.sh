#!/usr/bin/env bash
# Se ejecuta UNA vez en la VM (Debian/Ubuntu), con los ficheros copiados en /tmp/halfline-src (futdata/ y deploy/).
# Uso: sudo NTFY_TOPIC=<tema-largo-y-aleatorio> BUCKET=gs://<bucket> bash vm_setup.sh
# La VM necesita el scope devstorage.read_write y su cuenta de servicio objectCreator + objectViewer en el bucket.
set -euo pipefail
: "${NTFY_TOPIC:?define NTFY_TOPIC}"
: "${BUCKET:?define BUCKET}"

apt-get update -qq && apt-get install -y -qq python3-venv rsync zstd
id halfline &>/dev/null || useradd --system --create-home halfline
mkdir -p /opt/halfline/futdata /opt/halfline/deploy
cp /tmp/halfline-src/deploy/push_bucket.sh /opt/halfline/deploy/
for f in __init__ common polymarket polymarket_live monitor; do cp "/tmp/halfline-src/futdata/$f.py" /opt/halfline/futdata/; done
python3 -m venv /opt/halfline/.venv
/opt/halfline/.venv/bin/pip install -q requests websockets psutil zstandard
mkdir -p /opt/halfline/data && chown -R halfline: /opt/halfline

printf "NTFY_TOPIC=%s\nBUCKET=%s\n" "$NTFY_TOPIC" "$BUCKET" > /etc/halfline.env && chmod 600 /etc/halfline.env
cp /tmp/halfline-src/deploy/{polymarket-live.service,halfline-push.service,halfline-push.timer} /etc/systemd/system/
systemctl daemon-reload && systemctl enable --now polymarket-live halfline-push.timer
systemctl status polymarket-live --no-pager
