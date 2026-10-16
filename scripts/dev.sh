#!/usr/bin/env bash
# Arranca la API de datos (127.0.0.1:8000) y el frontend (http://localhost:5173).
set -e
cd "$(dirname "$0")/.."
python3 -m futdata.api &
API=$!
trap 'kill $API 2>/dev/null' EXIT
npm run dev --prefix web
