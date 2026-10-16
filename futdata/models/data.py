"""Tabla base para los modelos: un partido por fila con goles, xG y probabilidades del mercado.

Mercado (cuotas medias de Football-Data, sin margen con el método de potencia, futdata.models.margin):
  - mkt_p_home/draw/away, mkt_p_over: pre-cierre (viernes o martes). Válidas para predecir.
  - close_p_*: cierre. Solo como referencia.
  - bfe_p_*, bfe_close_p_*: Betfair Exchange (bolsa de apuestas) pre-cierre y cierre (desde 2024/25).
  - max_*, max_close_*: mejor cuota entre casas; b365_*, b365_close_*: Bet365.
  - *_odds_*: cuotas medias con margen (para simular apuestas).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from futdata.common import RAW, fd_code
from futdata.matches import PROCESSED
from futdata.models.margin import fair

MARKETS = {  # prefijo -> {etiqueta: columna de Football-Data}
    "mkt": {"home": "AvgH", "draw": "AvgD", "away": "AvgA"},
    "close": {"home": "AvgCH", "draw": "AvgCD", "away": "AvgCA"},
    "bfe": {"home": "BFEH", "draw": "BFED", "away": "BFEA"},          # Betfair Exchange pre-cierre
    "bfe_close": {"home": "BFECH", "draw": "BFECD", "away": "BFECA"},  # Betfair Exchange cierre
    "max": {"home": "MaxH", "draw": "MaxD", "away": "MaxA"},          # mejor cuota entre casas, pre-cierre
    "max_close": {"home": "MaxCH", "draw": "MaxCD", "away": "MaxCA"},
    "b365": {"home": "B365H", "draw": "B365D", "away": "B365A"},
    "b365_close": {"home": "B365CH", "draw": "B365CD", "away": "B365CA"},
    "mkt_ou": {"over": "Avg>2.5", "under": "Avg<2.5"},
    "close_ou": {"over": "AvgC>2.5", "under": "AvgC<2.5"},
}


def market_probs(matches: pd.DataFrame) -> pd.DataFrame:
    parts = []
    for (league, season), group in matches.groupby(["league", "season"]):
        csv = pd.read_csv(RAW / "football_data" / fd_code(season) / f"{league}.csv",
                          encoding="latin-1", on_bad_lines="skip")
        src = csv.loc[group.fd_row.values]
        out = pd.DataFrame({"match_id": group.match_id.values})
        for prefix, cols in MARKETS.items():
            odds = np.column_stack([pd.to_numeric(src.get(c), errors="coerce") if c in src
                                    else np.full(len(src), np.nan) for c in cols.values()])
            probs = fair(odds)
            name = prefix.replace("_ou", "")
            for i, label in enumerate(cols):
                out[f"{name}_odds_{label}"] = odds[:, i]
            if prefix.endswith("_ou"):
                out[f"{name}_p_over"] = probs[:, 0]
            else:
                for i, label in enumerate(cols):
                    out[f"{name}_p_{label}"] = probs[:, i]
        parts.append(out)
    return pd.concat(parts, ignore_index=True)


def load() -> pd.DataFrame:
    """Partidos jugados, ordenados por hora de inicio, con goles, xG, npxG y mercado."""
    matches = pd.read_parquet(PROCESSED / "matches.parquet")
    matches["kickoff"] = matches["kickoff_utc"].fillna(
        matches["date"].dt.tz_localize("UTC") + pd.Timedelta(hours=15))
    stats = pd.read_parquet(PROCESSED / "team_match_stats.parquet")
    xg = stats.pivot_table(index="match_id", columns="side",
                           values=["pa_expected_goals", "pa_expected_goals_non_penalty"])
    xg.columns = [f"{side}_{'npxg' if 'non_penalty' in v else 'xg'}" for v, side in xg.columns]
    out = (matches[["match_id", "league", "season", "date", "kickoff", "home", "away",
                    "home_goals", "away_goals", "fd_row"]]
           .join(xg, on="match_id")
           .merge(market_probs(matches), on="match_id", how="left"))
    out["result"] = np.select([out.home_goals > out.away_goals, out.home_goals == out.away_goals],
                              [0, 1], 2)  # 0 local, 1 empate, 2 visitante
    out["over"] = (out.home_goals + out.away_goals > 2.5).astype(int)
    return out.drop(columns="fd_row").sort_values(["kickoff", "match_id"]).reset_index(drop=True)
