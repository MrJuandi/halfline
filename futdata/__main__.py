"""CLI de descarga y estado de los datos crudos.

Uso:
  python -m futdata download [--sources football_data,espn,understat,transfermarkt,pitchapi]
                             [--first 2014] [--last N] [--leagues SP1,E0] [--force]
  python -m futdata status

Los logs van a la consola y a data/raw/_download.log. Un fallo en una fuente no impide
ejecutar las siguientes. football_data y transfermarkt no usan --leagues (se ignora para ellas).
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import date
from pathlib import Path

import pandas as pd

from futdata import espn, football_data, pitchapi, transfermarkt, understat
from futdata.common import FIRST_SEASON, LEAGUES, RAW, fd_code, log, seasons

SOURCES = ("football_data", "espn", "understat", "transfermarkt", "pitchapi")
LOG_FILE = RAW / "_download.log"


# ---------------------------------------------------------------- download

def _list_arg(allowed, upper: bool = False):
    """Parser de listas separadas por comas que sólo admite valores de 'allowed'."""
    def parse(text: str) -> list[str]:
        items = [x.strip().upper() if upper else x.strip() for x in text.split(",") if x.strip()]
        bad = [x for x in items if x not in allowed]
        if bad:
            raise argparse.ArgumentTypeError(
                f"valores no válidos: {', '.join(bad)} (válidos: {', '.join(allowed)})")
        return items
    return parse


def _setup_logging() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    console = logging.StreamHandler()
    console.setFormatter(fmt)
    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    file_handler.setFormatter(fmt)
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers = [console, file_handler]


def _run_source(source: str, args) -> dict:
    if source == "football_data":
        return football_data.download(args.first, args.last, args.force)
    if source == "espn":
        return espn.download(args.first, args.last, args.leagues, args.force)
    if source == "understat":
        return understat.download(args.first, args.last, args.leagues, args.force)
    if source == "transfermarkt":
        return transfermarkt.download(args.force)
    if source == "pitchapi":
        return pitchapi.download(args.first, args.last, args.leagues, args.force)
    raise ValueError(f"fuente desconocida: {source}")


def cmd_download(args) -> int:
    _setup_logging()
    log.info("download: fuentes=%s first=%s last=%s leagues=%s force=%s",
             args.sources, args.first, args.last, args.leagues, args.force)
    results: dict[str, dict] = {}
    failed = False
    for source in args.sources:
        try:
            results[source] = _run_source(source, args)
        except Exception as exc:  # una fuente rota no impide las siguientes
            failed = True
            log.exception("%s: fallo inesperado", source)
            results[source] = {"exception": f"{type(exc).__name__}: {exc}"}
    print("\nResumen de descarga:")
    for source, stats in results.items():
        print(f"  {source:<16} {stats}")
    return 1 if failed else 0


# ---------------------------------------------------------------- status

def _fd_last_date(path: Path) -> str | None:
    try:
        df = pd.read_csv(path, encoding="latin-1", on_bad_lines="skip", usecols=["Date"], dtype=str)
    except (OSError, ValueError):
        return None
    parsed = pd.to_datetime(df["Date"], format="mixed", dayfirst=True, errors="coerce").dropna()
    return parsed.max().date().isoformat() if len(parsed) else None


def _count_label(counts: dict[int, int]) -> str:
    return " ".join(f"{season}:{n}" for season, n in counts.items())


def _status_rows() -> list[tuple[str, str, str, int, str]]:
    """Filas (fuente, liga, nº de ficheros por temporada, total, último partido)."""
    rows = []
    all_seasons = seasons(FIRST_SEASON)

    # Football-Data: un CSV por liga y temporada
    for league in LEAGUES:
        counts = {}
        last = None
        for season in all_seasons:
            path = football_data.OUT / fd_code(season) / f"{league}.csv"
            counts[season] = 1 if path.exists() else 0
            if path.exists():
                d = _fd_last_date(path)
                if d and (last is None or d > last):
                    last = d
        rows.append(("football_data", league, _count_label(counts), sum(counts.values()), last or "-"))

    # ESPN: scoreboards por mes y summaries por partido
    for league in LEAGUES:
        counts = {s: sum(espn.scoreboard_path(league, ym).exists() for ym in espn.season_months(s))
                  for s in all_seasons}
        rows.append(("espn/scoreboard", league, _count_label(counts), sum(counts.values()), "-"))
    for league in LEAGUES:
        counts = {}
        for s in all_seasons:
            folder = espn.OUT / "summary" / league / str(s)
            counts[s] = len(list(folder.glob("*.json"))) if folder.exists() else 0
        rows.append(("espn/summary", league, _count_label(counts), sum(counts.values()),
                     espn.last_completed_date(league) or "-"))

    # Understat: league JSON por temporada y match JSON por partido
    for league in LEAGUES:
        counts = {}
        last = None
        for season in all_seasons:
            path = understat.league_path(league, season)
            counts[season] = 1 if path.exists() else 0
            if path.exists():
                d = understat.last_result_date(_load_json(path))
                if d and (last is None or d > last):
                    last = d
        rows.append(("understat/league", league, _count_label(counts), sum(counts.values()), last or "-"))
    for league in LEAGUES:
        counts = {}
        for s in all_seasons:
            folder = understat.OUT / "match" / league / str(s)
            counts[s] = len(list(folder.glob("*.json"))) if folder.exists() else 0
        rows.append(("understat/match", league, _count_label(counts), sum(counts.values()), "-"))
    return rows


def _load_json(path: Path) -> dict:
    return json.loads(path.read_bytes())


def cmd_status(_args) -> int:
    rows = _status_rows()
    headers = ("FUENTE", "LIGA", "FICHEROS POR TEMPORADA (inicio:n)", "TOTAL", "ÚLTIMO PARTIDO")
    widths = [max(len(str(r[i])) for r in rows + [headers]) for i in range(5)]
    widths[2] = min(widths[2], 120)
    line = "  ".join(f"{{:<{w}}}" for w in widths)
    print(line.format(*headers).rstrip())
    print("  ".join("-" * w for w in widths))
    for row in rows:
        print(line.format(*row).rstrip())

    lm_path = transfermarkt.LAST_MODIFIED
    lm = lm_path.read_text(encoding="utf-8").strip() if lm_path.exists() else "no descargado"
    csv_ok = "sí" if transfermarkt.CSV_DIR.exists() else "no"
    print(f"\ntransfermarkt: last_modified = {lm} | csv extraído = {csv_ok}")
    print(f"Fecha de hoy: {date.today().isoformat()}")
    return 0


# ---------------------------------------------------------------- main

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m futdata", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    dl = sub.add_parser("download", help="descargar datos crudos")
    dl.add_argument("--sources", type=_list_arg(SOURCES), default=list(SOURCES),
                    help="fuentes separadas por comas (por defecto, todas)")
    dl.add_argument("--first", type=int, default=None, help=f"primera temporada (por defecto {FIRST_SEASON})")
    dl.add_argument("--last", type=int, default=None, help="última temporada (por defecto la actual)")
    dl.add_argument("--leagues", type=_list_arg(list(LEAGUES), upper=True), default=None,
                    help="ligas separadas por comas, p. ej. SP1,E0 (por defecto, todas)")
    dl.add_argument("--force", action="store_true", help="volver a descargar lo que ya existe")
    dl.set_defaults(func=cmd_download)

    st = sub.add_parser("status", help="ver qué datos hay descargados")
    st.set_defaults(func=cmd_status)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
