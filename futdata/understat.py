"""Understat: datos de liga por temporada (xG, tiros, partidos) y detalle de cada partido.

Destino:
  data/raw/understat/league/<LIGA>/<SSSS>.json   (getLeagueData: teams, players, dates)
  data/raw/understat/match/<LIGA>/<SSSS>/<id>.json (getMatchData: rosters, shots, ...)

Las ligas de temporadas cerradas se descargan una sola vez; la temporada en curso se vuelve a
descargar en cada ejecución. Los partidos sólo se piden si isResult == True y no existen ya.

Si Understat cae, las peticiones fallan una tras otra. Tras MAX_CONSECUTIVE_FAILURES fallos
seguidos (red, HTTP 4xx/5xx o respuesta no válida) se aborta la fuente y se devuelve
stats["aborted"] = True. Un éxito reinicia el contador.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from futdata.common import FIRST_SEASON, LEAGUES, RAW, Client, current_season, fetch_to, log, seasons

SOURCE = "understat"
BASE = "https://understat.com"
OUT = RAW / SOURCE
MAX_CONSECUTIVE_FAILURES = 5
HEADERS = {"X-Requested-With": "XMLHttpRequest", "Referer": "https://understat.com/"}


class _Abort(Exception):
    """Se lanza al alcanzar MAX_CONSECUTIVE_FAILURES fallos seguidos."""


def _today() -> date:
    return date.today()


def _require_keys(*keys: str):
    """Devuelve un validador que exige que la respuesta sea un objeto JSON con esas claves."""
    def validate(content: bytes) -> None:
        data = json.loads(content)
        if not isinstance(data, dict) or any(k not in data for k in keys):
            raise ValueError(f"respuesta sin las claves esperadas {keys}")
    return validate


_validate_league = _require_keys("teams", "players", "dates")
_validate_match = _require_keys("rosters")


def league_path(league: str, season: int) -> Path:
    return OUT / "league" / league / f"{season}.json"


def match_path(league: str, season: int, match_id: str) -> Path:
    return OUT / "match" / league / str(season) / f"{match_id}.json"


def result_match_ids(league_data: dict) -> list[str]:
    """Ids de los partidos ya jugados (isResult == True) de un league JSON, sin duplicados."""
    seen: dict[str, None] = {}
    for match in league_data.get("dates", []):
        if match.get("isResult") is True:
            seen.setdefault(str(match["id"]), None)
    return list(seen)


def last_result_date(league_data: dict) -> str | None:
    """Fecha máxima ('YYYY-MM-DD') de los partidos jugados de un league JSON."""
    dates = [m["datetime"][:10] for m in league_data.get("dates", [])
             if m.get("isResult") is True and isinstance(m.get("datetime"), str)]
    return max(dates) if dates else None


def _get(client: Client, state: dict, stats: dict, url: str, path: Path, validate) -> bool:
    """fetch_to con contador de fallos consecutivos. Lanza _Abort al llegar al límite."""
    if fetch_to(client, SOURCE, url, path, validate=validate):
        state["failures"] = 0
        stats["ok"] += 1
        return True
    state["failures"] += 1
    stats["error"] += 1
    if state["failures"] >= MAX_CONSECUTIVE_FAILURES:
        raise _Abort()
    return False


def download(first: int | None = None, last: int | None = None, leagues: list[str] | None = None,
             force: bool = False) -> dict:
    client = Client(min_interval=1.5, headers=HEADERS)
    stats = {"ok": 0, "skipped": 0, "error": 0, "aborted": False}
    state = {"failures": 0}
    now = current_season(_today())
    try:
        for league in leagues or list(LEAGUES):
            understat_code = LEAGUES[league]["understat"]
            for season in seasons(first or FIRST_SEASON, last):
                # Datos de liga de la temporada
                path = league_path(league, season)
                if path.exists() and season < now and not force:
                    stats["skipped"] += 1
                else:
                    _get(client, state, stats, f"{BASE}/getLeagueData/{understat_code}/{season}",
                         path, _validate_league)
                if not path.exists():
                    continue
                # Detalle de los partidos jugados
                league_data = json.loads(path.read_bytes())
                for match_id in result_match_ids(league_data):
                    mpath = match_path(league, season, match_id)
                    if mpath.exists() and not force:
                        stats["skipped"] += 1
                        continue
                    _get(client, state, stats, f"{BASE}/getMatchData/{match_id}", mpath,
                         _validate_match)
    except _Abort:
        log.error("understat: abortado tras %d fallos consecutivos; se omite el resto de la fuente. "
                  "Reintentar más tarde.", MAX_CONSECUTIVE_FAILURES)
        stats["aborted"] = True
    log.info("understat: %s", stats)
    return stats
