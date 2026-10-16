"""Estadísticas por equipo y partido: una fila por (match_id, lado) con las columnas de cada fuente.

Fuentes y prefijos de columna:
  fd_   Football-Data: tiros, tiros a puerta, córners, faltas, tarjetas, goles al descanso.
  espn_ ESPN (boxscore): posesión, pases, centros, balones largos, entradas, intercepciones...
  pa_   PitchAPI (stats, periodo completo): xG y variantes, grandes ocasiones, duelos, regates...
        Las estadísticas "N (P%)" se separan en pa_<clave> (N) y pa_<clave>_pct (P).
  adv_  PitchAPI (advanced): xT, VAEP, pases y conducciones progresivas, PPDA, field tilt...
        Solo existe en la Premier desde 2021/22 y en el resto de ligas desde 2024/25.

Son estadísticas DEL PROPIO PARTIDO: no se pueden usar como variables para predecirlo.
Sirven para construir variables de forma con los partidos anteriores.

Salida: data/processed/team_match_stats.parquet
Uso:    python -m futdata.team_stats
"""
from __future__ import annotations

import json
import re
from concurrent.futures import ProcessPoolExecutor

import pandas as pd

from futdata.common import RAW, fd_code, log
from futdata.matches import PROCESSED

FD_COLUMNS = {  # columna de Football-Data (local, visitante) -> nombre
    "shots": ("HS", "AS"), "shots_on_target": ("HST", "AST"), "corners": ("HC", "AC"),
    "fouls": ("HF", "AF"), "yellow": ("HY", "AY"), "red": ("HR", "AR"), "ht_goals": ("HTHG", "HTAG"),
}
PA_RENAME = {"matchstats.headers.tackles": "tackles", "ShotsOnTarget": "shots_on_target",
             "ShotsOffTarget": "shots_off_target", "Offsides": "offsides",
             "BallPossesion": "possession", "big_chance_missed_title": "big_chance_missed"}
NUMBER = re.compile(r"-?\d+(?:\.\d+)?")


def _num(value):
    """'1.27' -> 1.27; '10 (50%)' -> (10.0, 50.0); '' o None -> None."""
    if value is None:
        return None
    found = NUMBER.findall(str(value))
    if not found:
        return None
    if "%" in str(value) and len(found) >= 2:
        return float(found[0]), float(found[1])
    return float(found[0])


def _snake(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()).strip("_")


# ---------------------------------------------------------------- por fuente

def football_data(matches: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (league, season), group in matches.groupby(["league", "season"]):
        csv = pd.read_csv(RAW / "football_data" / fd_code(season) / f"{league}.csv",
                          encoding="latin-1", on_bad_lines="skip")
        for m in group.itertuples():
            src = csv.loc[m.fd_row]
            for side, i in (("home", 0), ("away", 1)):
                row = {"match_id": m.match_id, "side": side}
                for name, cols in FD_COLUMNS.items():
                    row[f"fd_{name}"] = pd.to_numeric(src.get(cols[i]), errors="coerce")
                rows.append(row)
    return pd.DataFrame(rows)


def _espn_one(args):
    match_id, league, season, espn_id = args
    path = RAW / "espn" / "summary" / league / str(season) / f"{espn_id}.json"
    rows = []
    for team in json.loads(path.read_bytes())["boxscore"]["teams"]:
        row = {"match_id": match_id, "side": team.get("homeAway")}
        for stat in team.get("statistics", []):
            value = _num(stat.get("displayValue"))
            if isinstance(value, tuple):
                value = value[0]
            row[f"espn_{_snake(stat['name'])}"] = value
        rows.append(row)
    # ESPN rellena con ceros los equipos de los que no tiene estadísticas (posesión 0, todo 0):
    # son datos que faltan, no ceros. Si la posesión no suma 100, se anula la posesión.
    total = sum(r.get("espn_possession_pct") or 0 for r in rows)
    rows = [{k: (None if k.startswith("espn_") else v) for k, v in r.items()}
            if not r.get("espn_possession_pct") else r for r in rows]
    if abs(total - 100) > 1:
        for r in rows:
            r["espn_possession_pct"] = None
    return rows


def _pitchapi_one(args):
    match_id, league, season, pitchapi_id = args
    folder = RAW / "pitchapi" / "match" / league / str(season) / pitchapi_id
    rows = {"home": {"match_id": match_id, "side": "home"}, "away": {"match_id": match_id, "side": "away"}}
    stats = folder / "stats.json"
    if stats.exists():
        for period in json.loads(stats.read_bytes())["data"]["periods"]:
            if period["period"] != "All":
                continue
            for group in period["groups"]:
                for item in group["items"]:
                    key = item["key"]
                    if key.startswith("physical_metrics"):
                        continue  # casi nunca disponible
                    name = "pa_" + _snake(PA_RENAME.get(key, key))
                    for side in ("home", "away"):
                        if name in rows[side]:
                            continue  # la misma estadística aparece en dos grupos
                        value = _num(item.get(side))
                        if isinstance(value, tuple):
                            rows[side][name], rows[side][f"{name}_pct"] = value
                        else:
                            rows[side][name] = value
    advanced = folder / "advanced.json"
    if advanced.exists():
        data = json.loads(advanced.read_bytes())["data"]
        home_id = json.loads((folder / "match.json").read_bytes())["data"]["home_team"]["id"]
        for team in data["teams"]:
            side = "home" if team["team"]["id"] == home_id else "away"
            rows[side]["adv_actions"] = team.get("actions")
            for group, values in team.items():
                if not isinstance(values, dict) or group == "team":
                    continue
                for key, value in values.items():
                    if isinstance(value, dict):  # p. ej. sca_breakdown
                        for sub, v in value.items():
                            rows[side][f"adv_{key}_{sub}"] = v
                    else:
                        rows[side][f"adv_{key}"] = value
    return list(rows.values())


def _collect(func, jobs) -> pd.DataFrame:
    with ProcessPoolExecutor() as pool:
        return pd.DataFrame([row for rows in pool.map(func, jobs, chunksize=50) for row in rows])


# ---------------------------------------------------------------- tabla final

def build() -> pd.DataFrame:
    matches = pd.read_parquet(PROCESSED / "matches.parquet")
    base = pd.concat([
        matches.assign(side="home", team=matches.home, opponent=matches.away,
                       goals=matches.home_goals, goals_against=matches.away_goals),
        matches.assign(side="away", team=matches.away, opponent=matches.home,
                       goals=matches.away_goals, goals_against=matches.home_goals),
    ])[["match_id", "league", "season", "date", "kickoff_utc", "side", "team", "opponent",
        "goals", "goals_against"]]

    fd = football_data(matches)
    espn_jobs = [(m.match_id, m.league, m.season, m.espn_id)
                 for m in matches.dropna(subset=["espn_id"]).itertuples()]
    pa_jobs = [(m.match_id, m.league, m.season, m.pitchapi_id)
               for m in matches.dropna(subset=["pitchapi_id"]).itertuples()]
    espn = _collect(_espn_one, espn_jobs)
    pitch = _collect(_pitchapi_one, pa_jobs)

    out = base
    for part in (fd, espn, pitch):
        out = out.merge(part, on=["match_id", "side"], how="left")
    out = out.sort_values(["date", "match_id", "side"], ascending=[True, True, False]).reset_index(drop=True)
    PROCESSED.mkdir(parents=True, exist_ok=True)
    out.to_parquet(PROCESSED / "team_match_stats.parquet", index=False)
    log.info("team_match_stats: %d filas, %d columnas", *out.shape)
    return out


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    df = build()
    print(f"{len(df)} filas x {df.shape[1]} columnas")
    for prefix in ("fd_", "espn_", "pa_", "adv_"):
        cols = [c for c in df.columns if c.startswith(prefix)]
        filled = df[cols].notna().any(axis=1).mean() if cols else 0
        print(f"{prefix:6s} {len(cols):3d} columnas, filas con datos {filled:.1%}")
