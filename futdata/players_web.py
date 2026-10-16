"""Respuestas de la API para perfiles de jugador (a partir de futdata.player_styles)."""
from __future__ import annotations

import functools
import json

import numpy as np
import pandas as pd

from futdata.matches import PROCESSED
from futdata.player_styles import FEATURES
from futdata.web_data import _clean

KEYS = list(FEATURES)


@functools.lru_cache(maxsize=1)
def _frame() -> pd.DataFrame:
    return pd.read_parquet(PROCESSED / "player_styles.parquet")


@functools.lru_cache(maxsize=1)
def roles() -> dict:
    return json.loads((PROCESSED / "player_roles.json").read_text())


def player_map(season: int | str | None = None, league: str | None = None) -> dict:
    """season: año de inicio, o "now" para el estado actual (ventana de los últimos minutos)."""
    df = _frame()
    if season == "now" or season is None:
        sub = df[df.window == "now"]
        season = "now"
    else:
        season = int(season)
        sub = df[(df.season == season) & (df.window == "season")]
    if league:
        sub = sub[sub.league == league]
    cols = ["player_id", "name", "photo", "team", "league", "season", "minutes", "goals", "assists", "pc1", "pc2", "role"]
    seasons = sorted(int(s) for s in df[df.window == "season"].season.unique())
    return _clean({"season": season, "seasons": seasons, "roles": roles(),
                   "players": sub[cols].to_dict("records")})


def player_profile(player_id: str, season: int | str | None = None) -> dict | None:
    full = _frame()
    df = full[full.window == "season"]
    mine = full[full.player_id == player_id]
    if mine.empty:
        return None
    rows = mine[mine.window == "season"].sort_values("season")
    now_row = mine[mine.window == "now"]
    if season == "now" or (season is None and not now_row.empty):
        row = now_row.iloc[-1] if not now_row.empty else rows.iloc[-1]
    elif season is not None and (rows.season == int(season)).any():
        row = rows[rows.season == int(season)].iloc[-1]
    else:
        row = rows.iloc[-1] if not rows.empty else now_row.iloc[-1]
    z = df[[f"z_{k}" for k in KEYS]].to_numpy()
    me = row[[f"z_{k}" for k in KEYS]].to_numpy(dtype=float)
    dist = np.linalg.norm(z - me, axis=1)
    cand = df.assign(d=dist)
    cand = cand[cand.player_id != player_id].sort_values("d")
    cand = cand.drop_duplicates("player_id").head(10)
    max_d = float(np.quantile(dist, 0.5)) or 1.0
    is_now = row.get("window") == "now"
    return _clean({
        "window": "now" if is_now else "season",
        "window_from": row.get("window_from") if is_now else None,
        "window_to": row.get("window_to") if is_now else None,
        "this_season": row.get("this_season") if is_now else None,
        "short_sample": bool(row.get("short_sample")) if is_now else False,
        "has_now": not now_row.empty,
        "seasons": [int(s) for s in rows.season],
        "player_id": player_id, "name": row["name"], "photo": row["photo"], "team": row["team"],
        "league": row["league"], "season": int(row["season"]), "minutes": row["minutes"],
        "goals": row["goals"], "assists": row["assists"], "xg": row["xg"], "xa": row["xa"],
        "rating": row["rating_w"], "role": row["role"], "pc": [row["pc1"], row["pc2"]],
        "features": [{"key": k, "label": FEATURES[k], "value": row[f"v_{k}"], "z": row[f"z_{k}"],
                      "pct_role": row[f"p_{k}"]} for k in KEYS],
        "history": [{"season": int(r.season), "team": r.team, "league": r.league, "role": r.role,
                     "minutes": r.minutes, "pc": [r.pc1, r.pc2]} for r in rows.itertuples()],
        "similar": [{"player_id": r.player_id, "name": r.name, "photo": r.photo, "team": r.team,
                     "league": r.league, "season": int(r.season), "role": r.role,
                     "similarity": max(0.0, 1 - r.d / (2 * max_d))} for r in cand.itertuples()],
    })
