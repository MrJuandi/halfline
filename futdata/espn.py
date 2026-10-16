"""ESPN (API pública site.api.espn.com): calendario mensual y resúmenes de partido.

Destino:
  data/raw/espn/scoreboard/<LIGA>/<YYYYMM>.json        (calendario de un mes, julio -> junio)
  data/raw/espn/summary/<LIGA>/<SSSS>/<event_id>.json  (resumen de cada partido terminado)

Calendario: los meses que están más de 2 meses atrás se descargan sólo si falta el fichero;
el mes actual, el anterior y los futuros (hasta 2 meses vista) se vuelven a descargar en cada
ejecución. Resúmenes: sólo para eventos con status.type.completed == True; se saltan si ya existen.
"""
from __future__ import annotations

import json
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

from futdata.common import FIRST_SEASON, LEAGUES, RAW, Client, fetch_to, log, seasons

SOURCE = "espn"
BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer"
OUT = RAW / SOURCE
WORKERS = 8  # hilos para los resúmenes


def _today() -> date:
    return date.today()


def _require_keys(*keys: str):
    """Devuelve un validador que exige que la respuesta sea un objeto JSON con esas claves."""
    def validate(content: bytes) -> None:
        data = json.loads(content)
        if not isinstance(data, dict) or any(k not in data for k in keys):
            raise ValueError(f"respuesta sin las claves esperadas {keys}")
    return validate


_validate_scoreboard = _require_keys("events")
_validate_summary = _require_keys("boxscore")


def season_months(season: int) -> list[str]:
    """Meses de una temporada como 'YYYYMM': julio de season -> junio de season+1."""
    months = [f"{season}{m:02d}" for m in range(7, 13)]
    months += [f"{season + 1}{m:02d}" for m in range(1, 7)]
    return months


def scoreboard_path(league: str, yyyymm: str) -> Path:
    return OUT / "scoreboard" / league / f"{yyyymm}.json"


def summary_path(league: str, season: int, event_id: str) -> Path:
    return OUT / "summary" / league / str(season) / f"{event_id}.json"


def should_fetch_month(yyyymm: str, path: Path, force: bool, today: date) -> bool:
    """Decide si se descarga el calendario de un mes.

    - Más de 2 meses en el futuro: no se descarga.
    - Hace más de 2 meses (ni el mes actual, ni el anterior, ni los futuros): sólo si falta.
    - Resto (mes actual, anterior y hasta 2 meses vista): siempre.
    """
    idx = int(yyyymm[:4]) * 12 + int(yyyymm[4:]) - 1
    now = today.year * 12 + today.month - 1
    if idx > now + 2:
        return False
    if idx <= now - 2 and path.exists() and not force:
        return False
    return True


def completed_events(scoreboard: dict) -> list[tuple[str, str | None]]:
    """(id, fecha 'YYYY-MM-DD') de los eventos terminados de un scoreboard, sin duplicados."""
    seen: dict[str, str | None] = {}
    for event in scoreboard.get("events", []):
        try:
            completed = event["competitions"][0]["status"]["type"]["completed"] is True
        except (KeyError, IndexError, TypeError):
            completed = False
        if not completed:
            continue
        event_id = str(event["id"])
        if event_id not in seen:
            date_str = event.get("date")
            seen[event_id] = date_str[:10] if isinstance(date_str, str) else None
    return list(seen.items())


def _read_completed(league: str, months: list[str]) -> list[tuple[str, str | None]]:
    """Eventos terminados de los scoreboards guardados de los meses indicados (sin duplicados)."""
    seen: dict[str, str | None] = {}
    for ym in months:
        path = scoreboard_path(league, ym)
        if not path.exists():
            continue
        for event_id, date_str in completed_events(json.loads(path.read_bytes())):
            seen.setdefault(event_id, date_str)
    return list(seen.items())


def completed_event_ids(league: str, season: int) -> list[str]:
    """Ids de los partidos terminados de la liga/temporada, según los scoreboards guardados."""
    return [event_id for event_id, _ in _read_completed(league, season_months(season))]


def last_completed_date(league: str) -> str | None:
    """Fecha máxima ('YYYY-MM-DD') de un partido terminado en cualquier scoreboard guardado."""
    dates = [d for _, d in _read_completed(league, _all_months_on_disk(league)) if d]
    return max(dates) if dates else None


def _all_months_on_disk(league: str) -> list[str]:
    folder = OUT / "scoreboard" / league
    if not folder.exists():
        return []
    return sorted(p.stem for p in folder.glob("*.json"))


def download(first: int | None = None, last: int | None = None, leagues: list[str] | None = None,
             force: bool = False) -> dict:
    client = Client(min_interval=0.5)
    stats = {"ok": 0, "skipped": 0, "error": 0}
    local = threading.local()
    lock = threading.Lock()
    today = _today()
    for league in leagues or list(LEAGUES):
        espn_code = LEAGUES[league]["espn"]
        for season in seasons(first or FIRST_SEASON, last):
            # Calendario mensual
            for ym in season_months(season):
                path = scoreboard_path(league, ym)
                if not should_fetch_month(ym, path, force, today):
                    stats["skipped"] += 1
                    continue
                ok = fetch_to(client, SOURCE, f"{BASE}/{espn_code}/scoreboard", path,
                              params={"dates": ym, "limit": 500}, validate=_validate_scoreboard)
                stats["ok" if ok else "error"] += 1
            # Resúmenes de los partidos terminados, en paralelo (un cliente por hilo)
            def fetch_summary(event_id, league=league, season=season, espn_code=espn_code):
                path = summary_path(league, season, event_id)
                if path.exists() and not force:
                    key = "skipped"
                else:
                    if not hasattr(local, "client"):
                        local.client = Client(min_interval=0.1)
                    ok = fetch_to(local.client, SOURCE, f"{BASE}/{espn_code}/summary", path,
                                  params={"event": event_id}, validate=_validate_summary)
                    key = "ok" if ok else "error"
                with lock:
                    stats[key] += 1

            with ThreadPoolExecutor(WORKERS) as pool:
                list(pool.map(fetch_summary, completed_event_ids(league, season)))
    log.info("espn: %s", stats)
    return stats
