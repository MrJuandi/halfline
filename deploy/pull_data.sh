#!/usr/bin/env bash
# Baja a local datos del colector desde el bucket. No borra nada ni en el bucket ni en la VM.
# La VM sube sola las horas cerradas (deploy/push_bucket.sh), así que aquí solo se baja lo que haga falta.
# El bucket es Coldline: leer cuesta ~0,02 $/GB más la salida a internet (~0,12 $/GB). Baja solo lo necesario.
# Uso: bash deploy/pull_data.sh                 solo el catálogo (meta/)
#      bash deploy/pull_data.sh 2026-11-20 ...  además esos días de ws/
#      bash deploy/pull_data.sh --size          cuánto ocupa cada día en el bucket
set -euo pipefail
BUCKET="${BUCKET:-gs://halfline-6787-polymarket-live}"
# gcloud storage lanza subprocesos con el python que lo ejecuta; con el de Anaconda se cuelgan (falta google.auth).
for py in "${CLOUDSDK_PYTHON:-}" /opt/homebrew/bin/python3 /usr/local/bin/python3; do
  [ -x "$py" ] && { export CLOUDSDK_PYTHON="$py"; break; }
done
DEST="$(cd "$(dirname "$0")/.." && pwd)/data/raw/polymarket_live"

if [ "${1:-}" = --size ]; then gcloud storage du -s "$BUCKET/ws/*" | sort -k2; exit 0; fi

mkdir -p "$DEST/meta" "$DEST/ws"
gcloud storage rsync "$BUCKET/meta" "$DEST/meta"
for day in "$@"; do
  mkdir -p "$DEST/ws/$day"
  gcloud storage rsync "$BUCKET/ws/$day" "$DEST/ws/$day"
done
echo "OK: datos en $DEST"
