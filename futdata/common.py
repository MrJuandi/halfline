"""Utilidades compartidas: rutas, ligas, temporadas, cliente HTTP y registro de descargas.

Regla del proyecto: todo lo descargado se guarda en data/raw/<fuente>/ tal cual llega,
sin transformar, y cada descarga se apunta en data/raw/_manifest.jsonl.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import tempfile
import time
from datetime import date, datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
MANIFEST = RAW / "_manifest.jsonl"

FIRST_SEASON = 2021  # PitchAPI (xG) empieza en 2021/22

# Código interno -> códigos en cada fuente
LEAGUES = {
    "SP1": {"name": "LaLiga", "espn": "esp.1", "understat": "La_liga"},
    "E0": {"name": "Premier League", "espn": "eng.1", "understat": "EPL"},
    "I1": {"name": "Serie A", "espn": "ita.1", "understat": "Serie_A"},
    "D1": {"name": "Bundesliga", "espn": "ger.1", "understat": "Bundesliga"},
    "F1": {"name": "Ligue 1", "espn": "fra.1", "understat": "Ligue_1"},
}

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128 Safari/537.36"
)

log = logging.getLogger("futdata")


def current_season(today: date | None = None) -> int:
    """Año de inicio de la temporada en curso (la temporada empieza en julio)."""
    today = today or date.today()
    return today.year if today.month >= 7 else today.year - 1


def seasons(first: int = FIRST_SEASON, last: int | None = None) -> list[int]:
    """Años de inicio de temporada, de first a last (incluido)."""
    last = current_season() if last is None else last
    return list(range(first, last + 1))


def fd_code(season: int) -> str:
    """2014 -> '1415' (código de temporada de Football-Data)."""
    return f"{season % 100:02d}{(season + 1) % 100:02d}"


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Client:
    """Cliente HTTP con pausa mínima entre peticiones y reintentos con espera creciente."""

    def __init__(self, min_interval: float = 1.0, retries: int = 4, timeout: float = 30.0,
                 headers: dict | None = None):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT, "Accept-Encoding": "gzip, deflate"})
        if headers:
            self.session.headers.update(headers)
        self.min_interval = min_interval
        self.retries = retries
        self.timeout = timeout
        self._last = 0.0

    def get(self, url: str, **kwargs) -> requests.Response:
        """GET con reintentos ante errores de red, 429 y 5xx. Lanza la última excepción."""
        error: Exception | None = None
        for attempt in range(self.retries):
            wait = self.min_interval - (time.monotonic() - self._last)
            if wait > 0:
                time.sleep(wait)
            self._last = time.monotonic()
            try:
                response = self.session.get(url, timeout=self.timeout, **kwargs)
                if response.status_code == 429 or response.status_code >= 500:
                    raise requests.HTTPError(f"HTTP {response.status_code}", response=response)
                response.raise_for_status()
                return response
            except requests.RequestException as exc:
                error = exc
                status = getattr(getattr(exc, "response", None), "status_code", None)
                if status is not None and 400 <= status < 500 and status != 429:
                    break  # error del cliente: no tiene sentido reintentar
                retry_after = exc.response.headers.get("Retry-After") if status == 429 else None
                try:
                    pause = float(retry_after) if retry_after else min(60, 2 ** attempt * 3)
                except ValueError:
                    pause = min(60, 2 ** attempt * 3)
                time.sleep(pause)
        assert error is not None
        raise error


def write_raw(path: Path, content: bytes) -> str:
    """Escritura atómica (fichero temporal + rename). Devuelve el sha256 del contenido."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".tmp_")
    with os.fdopen(fd, "wb") as fh:
        fh.write(content)
    os.replace(tmp, path)
    return hashlib.sha256(content).hexdigest()


def record(source: str, url: str, path: Path | None, status: str, sha256: str | None = None,
           detail: str | None = None) -> None:
    """Añade una línea al manifiesto de descargas."""
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "fetched_at_utc": utcnow(), "source": source, "url": url,
        "path": str(path.relative_to(ROOT)) if path else None,
        "status": status, "sha256": sha256, "detail": detail,
    }
    with MANIFEST.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")


def fetch_to(client: Client, source: str, url: str, path: Path, *, params: dict | None = None,
             validate=None) -> bool:
    """Descarga url a path y la registra. validate(bytes) puede lanzar ValueError.

    Devuelve True si se guardó; False si falló (el fallo queda en el manifiesto).
    """
    full_url = url if not params else requests.Request("GET", url, params=params).prepare().url
    try:
        content = client.get(url, params=params).content
        if validate:
            validate(content)
        sha = write_raw(path, content)
        record(source, full_url, path, "ok", sha)
        return True
    except (requests.RequestException, ValueError) as exc:
        log.warning("%s: fallo en %s: %s", source, full_url, exc)
        record(source, full_url, None, "error", detail=str(exc)[:300])
        return False


def validate_json(content: bytes) -> None:
    json.loads(content)
