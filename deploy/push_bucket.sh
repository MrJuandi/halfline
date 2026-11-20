#!/usr/bin/env bash
# Corre en la VM (halfline-push.timer): sube al bucket las horas cerradas y el catálogo de días pasados,
# y borra de la VM solo lo que está verificado en el bucket.
# Por fichero: test de integridad local -> subir sin sobrescribir -> comparar md5 local/bucket -> borrar local.
# Si algo falla con un fichero, se queda en la VM y se reintenta en la siguiente pasada.
# Uso: BUCKET=gs://<bucket> bash push_bucket.sh   (DATA_DIR opcional)
set -uo pipefail
: "${BUCKET:?define BUCKET, p. ej. gs://halfline-6787-polymarket-live}"
DATA_DIR="${DATA_DIR:-/opt/halfline/data/raw/polymarket_live}"
exec 9>"$DATA_DIR/.push.lock"; flock -n 9 || { echo "Otra subida en curso"; exit 0; }
cd "$DATA_DIR" || exit 1

today="$(date -u +%F)"
files="$( { find ws -name '*.zst' -o -name '*.gz'; find meta -name '*.jsonl' ! -name "$today.jsonl"; } | sort )"
[ -n "$files" ] || { echo "Nada que subir"; exit 0; }

ok=0; fail=0
while read -r f; do
  case "$f" in
    *.zst) zstd -tq "$f" ;;
    *.gz) gzip -t "$f" ;;
    *) true ;;
  esac || { echo "ERROR: $f corrupto, se deja en la VM"; fail=$((fail + 1)); continue; }
  dest="$BUCKET/$f"
  gcloud storage cp --no-clobber --quiet "$f" "$dest" >/dev/null 2>&1
  local_md5="$(openssl dgst -md5 -binary "$f" | base64)"  # mismo formato que md5_hash de GCS
  remote_md5="$(gcloud storage objects describe "$dest" --format='value(md5_hash)' 2>/dev/null)"
  if [ -n "$local_md5" ] && [ "$local_md5" = "$remote_md5" ]; then
    rm -f -- "$f"; ok=$((ok + 1))
  else
    echo "ERROR: $f no coincide con el bucket (local=$local_md5 bucket=$remote_md5), se deja en la VM"
    fail=$((fail + 1))
  fi
done <<< "$files"
find ws -mindepth 1 -type d -empty -delete
echo "Subidos y borrados: $ok. Fallidos: $fail."
[ "$fail" -eq 0 ]
