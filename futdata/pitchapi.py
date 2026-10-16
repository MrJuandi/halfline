"""PitchAPI (api.pitchapi.dev): xG por tiro, estadísticas avanzadas de equipo y jugador,
mapas de calor, eventos, alineaciones, momentum, xT/VAEP y redes de pase.

Cobertura comprobada (13/10/2026) para las 5 ligas:
  - 2021/22 -> actual: partido, tiros con xG, estadísticas, jugadores, alineaciones, eventos.
  - Mapas de calor y analítica avanzada (heatmaps, advanced*): Premier desde 2021/22;
    LaLiga, Serie A, Bundesliga y Ligue 1 solo desde 2024/25. Para el resto la API
    responde 404 ANALYTICS_UNAVAILABLE y se guarda un marcador para no volver a pedirlo.
    Si los PROBE primeros partidos de una temporada no tienen analítica, no se piden en el resto.
  - Límite del servidor: unas 11 peticiones/s sostenidas por clave; el cliente respeta Retry-After.
PitchAPI no publica términos de uso ni el proveedor original de los datos: declararlo al usarlos.

Requiere la variable PITCHAPI_KEY (en el entorno o en el fichero .env de la raíz, excluido de git).

Destino:
  data/raw/pitchapi/leagues.json
  data/raw/pitchapi/matches/<LIGA>/<SSSS>.json                 (partidos de la temporada)
  data/raw/pitchapi/match/<LIGA>/<SSSS>/<match_id>/<endpoint>.json
  data/raw/pitchapi/match/<LIGA>/<SSSS>/<match_id>/<endpoint>.unavailable  (404 de la API)

Las listas de partidos de la temporada en curso se vuelven a pedir en cada ejecución; los
ficheros de cada partido terminado se piden una sola vez.
"""
from __future__ import annotations

import json
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

from futdata.common import FIRST_SEASON, ROOT, RAW, Client, current_season, fetch_to, log, record, seasons, \
    write_raw

SOURCE = "pitchapi"
BASE = "https://api.pitchapi.dev/v1"
OUT = RAW / SOURCE
FIRST_PITCHAPI_SEASON = 2021
LEAGUE_IDS = {"SP1": "l_0ErfuF", "E0": "l_4WFCIZ", "I1": "l_0ALvwF", "D1": "l_1Isor4", "F1": "l_3FJFUl"}
ENDPOINTS = {
    "match": "", "shots": "/shots", "stats": "/stats", "players": "/players", "lineups": "/lineups",
    "events": "/events", "momentum": "/momentum", "heatmaps": "/heatmaps", "advanced": "/advanced",
    "advanced_network": "/advanced/network", "advanced_players": "/advanced/players",
}
WORKERS = 16
ANALYTICS = ("heatmaps", "advanced", "advanced_network", "advanced_players")
PROBE = 10  # partidos que se prueban antes de dar por hecho que una temporada no tiene analítica


def api_key() -> str:
    key = os.environ.get("PITCHAPI_KEY")
    env = ROOT / ".env"
    if not key and env.exists():
        for line in env.read_text().splitlines():
            if line.startswith("PITCHAPI_KEY="):
                key = line.split("=", 1)[1].strip()
    if not key:
        raise RuntimeError("Falta PITCHAPI_KEY (entorno o .env)")
    return key


def season_label(season: int) -> str:
    return f"{season}/{season + 1}"


def _validate(content: bytes) -> None:
    if "data" not in json.loads(content):
        raise ValueError("respuesta sin clave 'data'")


def _matches(path: Path) -> list[dict]:
    data = json.loads(path.read_bytes())["data"]
    return data.get("matches", data) if isinstance(data, dict) else data


def _fetch_match(client: Client, folder: Path, match_id: str, stats: dict, lock: threading.Lock,
                 endpoints: dict = ENDPOINTS) -> None:
    for name, suffix in endpoints.items():
        path = folder / f"{name}.json"
        marker = folder / f"{name}.unavailable"
        if path.exists() or marker.exists():
            key = "skipped"
        else:
            url = f"{BASE}/matches/{match_id}{suffix}"
            try:
                content = client.get(url).content
                _validate(content)
                record(SOURCE, url, path, "ok", write_raw(path, content))
                key = "ok"
            except requests.HTTPError as exc:
                response = exc.response
                if response is not None and response.status_code == 404:
                    write_raw(marker, response.content)
                    record(SOURCE, url, marker, "unavailable", detail=response.text[:200])
                    key = "unavailable"
                else:
                    record(SOURCE, url, None, "error", detail=str(exc)[:300])
                    key = "error"
            except (requests.RequestException, ValueError) as exc:
                record(SOURCE, url, None, "error", detail=str(exc)[:300])
                key = "error"
        with lock:
            stats[key] += 1


def download(first: int | None = None, last: int | None = None, leagues: list[str] | None = None,
             force: bool = False) -> dict:
    headers = {"X-API-KEY": api_key()}
    client = Client(min_interval=0.2, headers=headers)
    stats = {"ok": 0, "skipped": 0, "unavailable": 0, "error": 0}
    fetch_to(client, SOURCE, f"{BASE}/leagues", OUT / "leagues.json", validate=_validate)
    now = current_season()
    first = max(first or FIRST_SEASON, FIRST_PITCHAPI_SEASON)
    local = threading.local()
    lock = threading.Lock()

    def worker(job, endpoints=ENDPOINTS):
        if not hasattr(local, "client"):
            local.client = Client(min_interval=0.05, retries=10, headers=headers)
        _fetch_match(local.client, *job, stats, lock, endpoints)

    for league in leagues or list(LEAGUE_IDS):
        for season in seasons(first, last):
            path = OUT / "matches" / league / f"{season}.json"
            if force or season >= now or not path.exists():
                fetch_to(client, SOURCE, f"{BASE}/leagues/{LEAGUE_IDS[league]}/matches", path,
                         params={"season": season_label(season)}, validate=_validate)
            if not path.exists():
                stats["error"] += 1
                continue
            jobs = [(OUT / "match" / league / str(season) / m["id"], m["id"])
                    for m in _matches(path) if m.get("status") == "finished"]
            # Primero unos pocos partidos con todos los endpoints; si ninguno tiene analítica
            # (mapas de calor, xT/VAEP), el resto de la temporada se pide sin esos endpoints.
            probe, rest = jobs[:PROBE], jobs[PROBE:]
            with ThreadPoolExecutor(WORKERS) as pool:
                list(pool.map(worker, probe))
            has_analytics = any((folder / "advanced.json").exists() for folder, _ in probe)
            endpoints = ENDPOINTS if has_analytics else {
                k: v for k, v in ENDPOINTS.items() if k not in ANALYTICS}
            if not has_analytics:
                log.info("pitchapi %s %s: sin analítica avanzada, se omiten %s", league, season, ANALYTICS)
            with ThreadPoolExecutor(WORKERS) as pool:
                list(pool.map(lambda job: worker(job, endpoints), rest))
            log.info("pitchapi %s %s: %d partidos, %s", league, season, len(jobs), stats)
    log.info("pitchapi: %s", stats)
    return stats
