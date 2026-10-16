"""Football-Data.co.uk: CSV por liga y temporada, fixtures.csv y notes.txt.

Destino:
  data/raw/football_data/<SSSS>/<LIGA>.csv   (SSSS = 1415, 1516, ...)
  data/raw/football_data/fixtures.csv        (próximos partidos con cuotas pre-cierre)
  data/raw/football_data/notes.txt           (diccionario de columnas)

Las temporadas cerradas se descargan una sola vez; la temporada en curso,
fixtures.csv y notes.txt se vuelven a descargar en cada ejecución.
"""
from __future__ import annotations

from futdata.common import FIRST_SEASON, LEAGUES, RAW, Client, current_season, fd_code, fetch_to, log, seasons

SOURCE = "football_data"
BASE = "https://www.football-data.co.uk"
OUT = RAW / SOURCE


def _validate_csv(content: bytes) -> None:
    head = content[:300].decode("latin-1")
    if "HomeTeam" not in head or "FTR" not in head:
        raise ValueError("La respuesta no parece un CSV de resultados de Football-Data")


def _validate_fixtures(content: bytes) -> None:
    if "HomeTeam" not in content[:300].decode("latin-1"):
        raise ValueError("La respuesta no parece el fixtures.csv de Football-Data")


def download(first: int | None = None, last: int | None = None, force: bool = False) -> dict:
    client = Client(min_interval=1.0)
    now_season = current_season()
    stats = {"ok": 0, "skipped": 0, "error": 0}
    for season in seasons(first or FIRST_SEASON, last):
        for league in LEAGUES:
            path = OUT / fd_code(season) / f"{league}.csv"
            if path.exists() and season < now_season and not force:
                stats["skipped"] += 1
                continue
            url = f"{BASE}/mmz4281/{fd_code(season)}/{league}.csv"
            ok = fetch_to(client, SOURCE, url, path, validate=_validate_csv)
            stats["ok" if ok else "error"] += 1
    for name, validate in (("fixtures.csv", _validate_fixtures), ("notes.txt", None)):
        ok = fetch_to(client, SOURCE, f"{BASE}/{name}", OUT / name, validate=validate)
        stats["ok" if ok else "error"] += 1
    log.info("football_data: %s", stats)
    return stats
