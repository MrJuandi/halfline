#!/usr/bin/env bash
# Baja a local el catálogo y las horas cerradas (.gz) y borra de la VM solo lo que ha quedado verificado.
# Orden: listar -> copiar -> gzip -t en local -> comparar sha256 local/remoto -> borrar en la VM esos mismos ficheros.
# Si cualquier paso falla, no se borra nada. Es seguro repetirlo o interrumpirlo en cualquier momento.
# Requiere haber ejecutado antes: gcloud compute config-ssh
# Uso: HOST=halfline-collector.<zona>.<proyecto> bash deploy/pull_data.sh
#      HOST=local REMOTE_DIR=<ruta> bash deploy/pull_data.sh   (prueba sin VM)
set -euo pipefail
: "${HOST:?define HOST, p. ej. halfline-collector.europe-west1-b.mi-proyecto}"
REMOTE_DIR="${REMOTE_DIR:-/opt/halfline/data/raw/polymarket_live}"
DEST="$(cd "$(dirname "$0")/.." && pwd)/data/raw/polymarket_live"
mkdir -p "$DEST/ws" "$DEST/meta"

if [ "$HOST" = local ]; then
  remote() { bash -c "$1"; }; SRC="$REMOTE_DIR"
else
  remote() { ssh "$HOST" "$1"; }; SRC="$HOST:$REMOTE_DIR"
fi

# catálogo: se copia sin borrar (el fichero del día sigue creciendo)
rsync -a "$SRC/meta/" "$DEST/meta/"

LIST="$(mktemp)"; trap 'rm -f "$LIST" "$LIST.remote" "$LIST.local"' EXIT
remote "cd $REMOTE_DIR/ws 2>/dev/null && find . -name '*.gz' | sed 's|^\./||' | sort" > "$LIST"
if [ ! -s "$LIST" ]; then echo "No hay horas cerradas que bajar."; exit 0; fi
echo "$(wc -l < "$LIST" | tr -d ' ') ficheros en la VM"

rsync -a --files-from="$LIST" "$SRC/ws/" "$DEST/ws/"

(cd "$DEST/ws" && while read -r f; do gzip -t "$f"; done < "$LIST") || { echo "ERROR: gzip corrupto, no se borra nada"; exit 1; }

remote "cd $REMOTE_DIR/ws && xargs sha256sum --" < "$LIST" | sort > "$LIST.remote"
(cd "$DEST/ws" && xargs shasum -a 256 -- < "$LIST") | sort > "$LIST.local"
cmp -s "$LIST.remote" "$LIST.local" || { echo "ERROR: los hashes no coinciden, no se borra nada"; exit 1; }

remote "cd $REMOTE_DIR/ws && xargs rm -f --" < "$LIST"
echo "OK: $(wc -l < "$LIST" | tr -d ' ') ficheros descargados, verificados y borrados de la VM."
