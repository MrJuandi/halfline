"""Transfermarkt: dataset abierto en zip (jugadores, clubes, valoraciones, etc.).

Destino:
  data/raw/transfermarkt/transfermarkt-datasets.zip  (zip original)
  data/raw/transfermarkt/last_modified.txt           (cabecera Last-Modified del zip descargado)
  data/raw/transfermarkt/csv/                        (contenido del zip extraído; se sustituye entero)

Se compara la cabecera Last-Modified (HEAD) con la guardada; si coincide, no se descarga
(salvo force). Nota: el dataset está congelado con datos hasta el 6/7/2026 (anunciado por el
mantenedor), así que aunque se descargue de nuevo no habrá datos posteriores a esa fecha.
"""
from __future__ import annotations

import hashlib
import os
import shutil
import zipfile
from pathlib import Path

import requests

from futdata.common import RAW, Client, log, record, write_raw

SOURCE = "transfermarkt"
URL = "https://pub-e682421888d945d684bcae8890b0ec20.r2.dev/data/transfermarkt-datasets.zip"
OUT = RAW / SOURCE
ZIP = OUT / "transfermarkt-datasets.zip"
LAST_MODIFIED = OUT / "last_modified.txt"
CSV_DIR = OUT / "csv"
CHUNK_SIZE = 1024 * 1024  # 1 MB


def _remote_last_modified(client: Client) -> str | None:
    response = client.session.head(URL, allow_redirects=True, timeout=client.timeout)
    response.raise_for_status()
    return response.headers.get("Last-Modified")


def _download_zip(client: Client) -> None:
    """Descarga en streaming a un .tmp del mismo directorio, valida el zip y lo mueve a su sitio."""
    OUT.mkdir(parents=True, exist_ok=True)
    tmp = ZIP.with_name(ZIP.name + ".tmp")
    digest = hashlib.sha256()
    try:
        response = client.get(URL, stream=True)
        with open(tmp, "wb") as fh:
            for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
                if chunk:
                    fh.write(chunk)
                    digest.update(chunk)
        response.close()
        if not zipfile.is_zipfile(tmp):
            raise ValueError("el fichero descargado no es un zip válido")
        os.replace(tmp, ZIP)
    finally:
        tmp.unlink(missing_ok=True)
    record(SOURCE, URL, ZIP, "ok", digest.hexdigest())


def _extract_zip() -> None:
    """Extrae el zip en un directorio temporal y lo sustituye por data/raw/transfermarkt/csv/."""
    staging = OUT / "csv.tmp"
    shutil.rmtree(staging, ignore_errors=True)
    with zipfile.ZipFile(ZIP) as zf:
        zf.extractall(staging)
    shutil.rmtree(CSV_DIR, ignore_errors=True)
    os.replace(staging, CSV_DIR)


def download(force: bool = False) -> dict:
    client = Client()
    stats = {"ok": 0, "skipped": 0, "error": 0}
    try:
        remote_lm = _remote_last_modified(client)
    except requests.RequestException as exc:
        log.warning("%s: fallo en HEAD %s: %s", SOURCE, URL, exc)
        record(SOURCE, URL, None, "error", detail=f"HEAD: {exc}"[:300])
        stats["error"] += 1
        log.info("transfermarkt: %s", stats)
        return stats

    local_lm = LAST_MODIFIED.read_text(encoding="utf-8").strip() if LAST_MODIFIED.exists() else None
    if not force and remote_lm and ZIP.exists() and CSV_DIR.exists() and local_lm == remote_lm:
        stats["skipped"] += 1
        log.info("transfermarkt: sin cambios desde %s", remote_lm)
        return stats

    try:
        _download_zip(client)
        _extract_zip()
        if remote_lm:
            write_raw(LAST_MODIFIED, remote_lm.encode("utf-8"))
        else:
            LAST_MODIFIED.unlink(missing_ok=True)  # sin cabecera no podremos saltar la próxima vez
        stats["ok"] += 1
    except (requests.RequestException, ValueError, zipfile.BadZipFile, OSError) as exc:
        log.warning("%s: fallo en %s: %s", SOURCE, URL, exc)
        record(SOURCE, URL, None, "error", detail=str(exc)[:300])
        stats["error"] += 1
    log.info("transfermarkt: %s", stats)
    return stats
