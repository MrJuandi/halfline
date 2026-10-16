"""Tabla maestra de partidos: une Football-Data, ESPN y PitchAPI con un identificador común.

Football-Data es la referencia: sus nombres de equipo son los canónicos y cada fila suya es un
partido. Los nombres de ESPN y PitchAPI se traducen con un diccionario que se aprende de los
propios partidos: en cada liga y temporada, un partido de la otra fuente con la misma fecha
(±1 día) y el mismo marcador que uno de Football-Data vota por "su local = local de FD" y
"su visitante = visitante de FD". Cada nombre se asigna al canónico con mayoría clara, o con
al menos MIN_VOTES votos si el nombre es idéntico (equipos recién ascendidos, con pocos partidos).

Salidas:
  data/processed/matches.parquet   un partido por fila con los ids de cada fuente
  data/processed/team_names.csv    diccionario de nombres por fuente y liga (con votos)

Uso:  python -m futdata.matches
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

from futdata.common import FIRST_SEASON, LEAGUES, RAW, ROOT, fd_code, log, seasons

PROCESSED = ROOT / "data" / "processed"
MAX_DAYS = 1          # diferencia máxima de fecha entre fuentes (husos horarios, fechas locales)
MIN_VOTES = 3         # votos mínimos para aceptar un nombre
MIN_SHARE = 0.6       # proporción mínima de votos del nombre ganador


# ---------------------------------------------------------------- carga por fuente

def load_football_data() -> pd.DataFrame:
    rows = []
    for season in seasons(FIRST_SEASON):
        for league in LEAGUES:
            path = RAW / "football_data" / fd_code(season) / f"{league}.csv"
            if not path.exists():
                continue
            df = pd.read_csv(path, encoding="latin-1", on_bad_lines="skip")
            df.columns = [c.replace("ï»¿", "").lstrip("﻿") for c in df.columns]
            df = df.dropna(subset=["HomeTeam", "AwayTeam", "FTHG", "FTAG"])
            rows.append(pd.DataFrame({
                "league": league, "season": season,
                "date": pd.to_datetime(df["Date"], dayfirst=True, format="mixed").dt.normalize(),
                "time_uk": df.get("Time"),
                "home": df["HomeTeam"].str.strip(), "away": df["AwayTeam"].str.strip(),
                "home_goals": df["FTHG"].astype(int), "away_goals": df["FTAG"].astype(int),
                "fd_row": df.index,
            }))
    return pd.concat(rows, ignore_index=True)


def load_espn() -> pd.DataFrame:
    rows = []
    for path in sorted((RAW / "espn" / "summary").glob("*/*/*.json")):
        league, season = path.parts[-3], int(path.parts[-2])
        comp = json.loads(path.read_bytes())["header"]["competitions"][0]
        side = {c["homeAway"]: c for c in comp["competitors"]}
        try:
            hg, ag = int(side["home"]["score"]), int(side["away"]["score"])
        except (KeyError, TypeError, ValueError):
            continue
        rows.append({"league": league, "season": season, "espn_id": path.stem,
                     "kickoff_utc": pd.Timestamp(comp["date"]),
                     "home": side["home"]["team"]["displayName"],
                     "away": side["away"]["team"]["displayName"],
                     "home_goals": hg, "away_goals": ag})
    df = pd.DataFrame(rows)
    df["date"] = df["kickoff_utc"].dt.tz_convert(None).dt.normalize()
    return df


def load_pitchapi() -> pd.DataFrame:
    rows = []
    for path in sorted((RAW / "pitchapi" / "matches").glob("*/*.json")):
        league, season = path.parent.name, int(path.stem)
        data = json.loads(path.read_bytes())["data"]
        for m in data.get("matches", data) if isinstance(data, dict) else data:
            if m.get("status") != "finished":
                continue
            rows.append({"league": league, "season": season, "pitchapi_id": m["id"],
                         "kickoff_utc": pd.Timestamp(m["time_utc"]),
                         "home": m["home_team"]["name"], "away": m["away_team"]["name"],
                         "home_goals": m["score_home"], "away_goals": m["score_away"]})
    df = pd.DataFrame(rows)
    df["date"] = df["kickoff_utc"].dt.tz_convert(None).dt.normalize()
    return df


# ---------------------------------------------------------------- diccionario de nombres

def learn_names(fd: pd.DataFrame, other: pd.DataFrame, source: str) -> pd.DataFrame:
    """Diccionario (liga, nombre en la fuente) -> nombre canónico de FD, por votos."""
    votes: dict[tuple, Counter] = defaultdict(Counter)
    key = ["league", "season", "home_goals", "away_goals"]
    pairs = other.merge(fd, on=key, suffixes=("_o", "_fd"))
    pairs = pairs[(pairs["date_o"] - pairs["date_fd"]).abs() <= pd.Timedelta(days=MAX_DAYS)]
    for row in pairs.itertuples():
        votes[(row.league, row.home_o)][row.home_fd] += 1
        votes[(row.league, row.away_o)][row.away_fd] += 1
    out = []
    for (league, name), counter in votes.items():
        best, n = counter.most_common(1)[0]
        total = sum(counter.values())
        out.append({"source": source, "league": league, "name": name, "canonical": best,
                    "votes": n, "share": round(n / total, 3),
                    "accepted": n >= MIN_VOTES and (n / total >= MIN_SHARE or name == best)})
    names = pd.DataFrame(out)
    # Un nombre canónico no puede recibir dos nombres distintos de la misma fuente y liga.
    dup = names[names.accepted].duplicated(["league", "canonical"], keep=False)
    if dup.any():
        log.warning("%s: nombres en conflicto:\n%s", source, names[names.accepted][dup])
    return names


# ---------------------------------------------------------------- unión

def attach(fd: pd.DataFrame, other: pd.DataFrame, names: pd.DataFrame, id_col: str) -> pd.DataFrame:
    """Añade a fd la columna id_col (y kickoff_utc) del partido equivalente de la otra fuente."""
    mapping = names[names.accepted].set_index(["league", "name"])["canonical"]
    o = other.copy()
    o["home_c"] = [mapping.get((l, n)) for l, n in zip(o.league, o.home)]
    o["away_c"] = [mapping.get((l, n)) for l, n in zip(o.league, o.away)]
    cand = fd.reset_index().merge(
        o[["league", "home_c", "away_c", "date", "home_goals", "away_goals", id_col, "kickoff_utc"]],
        left_on=["league", "home", "away"], right_on=["league", "home_c", "away_c"],
        suffixes=("", "_o"))
    cand = cand[(cand["date"] - cand["date_o"]).abs() <= pd.Timedelta(days=MAX_DAYS)]
    cand["score_ok"] = (cand.home_goals == cand.home_goals_o) & (cand.away_goals == cand.away_goals_o)
    cand = cand.sort_values("score_ok", ascending=False).drop_duplicates("index")
    out = fd.copy()
    out[id_col] = cand.set_index("index")[id_col]
    out[f"{id_col}_score_ok"] = cand.set_index("index")["score_ok"]
    if "kickoff_utc" not in out:
        out["kickoff_utc"] = cand.set_index("index")["kickoff_utc"]
    else:
        out["kickoff_utc"] = out["kickoff_utc"].fillna(cand.set_index("index")["kickoff_utc"])
    return out


def build() -> dict:
    fd = load_football_data()
    espn, pitch = load_espn(), load_pitchapi()
    names_espn = learn_names(fd, espn, "espn")
    names_pitch = learn_names(fd, pitch, "pitchapi")
    df = attach(fd, espn, names_espn, "espn_id")
    df = attach(df, pitch, names_pitch, "pitchapi_id")
    df.insert(0, "match_id", df["league"] + "_" + df["date"].dt.strftime("%Y%m%d") + "_"
              + df["home"].str.replace(" ", "") + "_" + df["away"].str.replace(" ", ""))
    PROCESSED.mkdir(parents=True, exist_ok=True)
    df.to_parquet(PROCESSED / "matches.parquet", index=False)
    pd.concat([names_espn, names_pitch]).sort_values(["source", "league", "canonical"]).to_csv(
        PROCESSED / "team_names.csv", index=False)

    report = {"football_data": len(fd), "espn": len(espn), "pitchapi": len(pitch)}
    for col, other in (("espn_id", espn), ("pitchapi_id", pitch)):
        report[f"{col} unidos"] = int(df[col].notna().sum())
        report[f"{col} marcador distinto"] = int((df[f"{col}_score_ok"] == False).sum())  # noqa: E712
        report[f"{col} sin unir (de la fuente)"] = int((~other[col].isin(df[col])).sum())
    report["nombres rechazados"] = int((~pd.concat([names_espn, names_pitch]).accepted).sum())
    return report


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    for k, v in build().items():
        print(f"{k:40s} {v}")
