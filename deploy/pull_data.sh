#!/usr/bin/env bash
# Baja a local el catálogo y los .gz ya cerrados; estos últimos se borran de la VM solo si llegaron bien (rsync --remove-source-files).
# Requiere haber ejecutado antes: gcloud compute config-ssh
# Uso: HOST=halfline-collector.<zona>.<proyecto> bash deploy/pull_data.sh
set -euo pipefail
: "${HOST:?define HOST, p. ej. halfline-collector.europe-west1-b.mi-proyecto}"
DEST="$(dirname "$0")/../data/raw/polymarket_live"
mkdir -p "$DEST"
SRC="$HOST:/opt/halfline/data/raw/polymarket_live"
# catálogo: se copia sin borrar (el fichero del día sigue creciendo)
rsync -av "$SRC/meta/" "$DEST/meta/"
# mensajes del websocket: solo horas cerradas (.gz), borradas de la VM tras copiarse
rsync -av --remove-source-files --include='*/' --include='*.gz' --exclude='*' "$SRC/ws/" "$DEST/ws/"
