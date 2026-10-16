"""Valor de mercado del once titular (Transfermarkt), por partido y equipo.

- xi_value: suma del último valor de mercado de cada titular ANTES del día del partido.
- xi_usual: media del xi_value del mismo club en sus 5 partidos de liga anteriores.
- xi_rel = log(xi_value / xi_usual): < 0 si sale un once peor que el habitual (bajas, rotaciones).

La alineación se conoce ~1 h antes del inicio: estas variables NO estaban disponibles cuando se
capturaron las cuotas pre-cierre (viernes o martes), pero sí antes del cierre.
Cobertura: hasta la temporada 2025/26 (el dataset se congeló el 6/7/2026).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from futdata.common import RAW

TM = RAW / "transfermarkt" / "csv"
TM_LEAGUE = {"SP1": "ES1", "E0": "GB1", "I1": "IT1", "D1": "L1", "F1": "FR1"}


def _games() -> pd.DataFrame:
    g = pd.read_csv(TM / "games.csv.gz", parse_dates=["date"],
                    usecols=["game_id", "competition_id", "season", "date", "home_club_id", "away_club_id",
                             "home_club_goals", "away_club_goals"])
    inv = {v: k for k, v in TM_LEAGUE.items()}
    g = g[g.competition_id.isin(inv) & (g.season >= 2020)].copy()
    g["league"] = g.competition_id.map(inv)
    return g


def _candidates(df: pd.DataFrame, games: pd.DataFrame) -> pd.DataFrame:
    """Pares (partido nuestro, partido de Transfermarkt) con misma liga, marcador y fecha (±1 día)."""
    cand = df[["match_id", "league", "date", "home", "away", "home_goals", "away_goals"]].merge(
        games, left_on=["league", "home_goals", "away_goals"],
        right_on=["league", "home_club_goals", "away_club_goals"])
    return cand[(cand.date_x - cand.date_y).abs() <= pd.Timedelta(days=1)]


def club_ids(df: pd.DataFrame, games: pd.DataFrame, cand: pd.DataFrame | None = None) -> pd.Series:
    """club_id de Transfermarkt por (liga, equipo), emparejado por votos entre los candidatos."""
    cand = _candidates(df, games) if cand is None else cand
    votes = pd.concat([cand[["league", "home", "home_club_id"]].set_axis(["league", "team", "club"], axis=1),
                       cand[["league", "away", "away_club_id"]].set_axis(["league", "team", "club"], axis=1)])
    return (votes.value_counts().reset_index().drop_duplicates(["league", "team"])
            .set_index(["league", "team"])["club"])


def link_games(df: pd.DataFrame, games: pd.DataFrame) -> pd.Series:
    """game_id de Transfermarkt para cada partido de df (NaN si no aparece).

    Los clubes se emparejan por votos: partidos con misma liga, marcador y fecha (±1 día).
    """
    cand = _candidates(df, games)
    best = club_ids(df, games, cand)
    cand = cand[(cand.home_club_id.values == best.reindex(list(zip(cand.league, cand.home))).values)
                & (cand.away_club_id.values == best.reindex(list(zip(cand.league, cand.away))).values)]
    return cand.drop_duplicates("match_id").set_index("match_id").game_id.reindex(df.match_id).set_axis(df.index)


def xi_values(games: pd.DataFrame) -> pd.DataFrame:
    """Una fila por (game_id, club_id) con el valor del once titular."""
    lu = pd.read_csv(TM / "game_lineups.csv.gz", usecols=["game_id", "player_id", "club_id", "type", "date"],
                     parse_dates=["date"])
    lu = lu[lu.game_id.isin(games.game_id) & (lu.type == "starting_lineup")].sort_values("date")
    val = pd.read_csv(TM / "player_valuations.csv.gz", usecols=["player_id", "date", "market_value_in_eur"],
                      parse_dates=["date"]).sort_values("date")
    lu = pd.merge_asof(lu, val, on="date", by="player_id", allow_exact_matches=False)  # valor previo al día
    out = lu.groupby(["game_id", "club_id"]).agg(xi_value=("market_value_in_eur", "sum"),
                                                 n_valued=("market_value_in_eur", "count")).reset_index()
    out = out.merge(games[["game_id", "date"]], on="game_id").sort_values("date")
    out["xi_usual"] = out.groupby("club_id").xi_value.transform(lambda s: s.shift(1).rolling(5, min_periods=1).mean())
    return out


def features(df: pd.DataFrame) -> pd.DataFrame:
    """Variables de once titular para cada partido de df (alineado por índice)."""
    games = _games()
    gid = link_games(df, games)
    xi = xi_values(games)
    g = games.set_index("game_id")
    out = pd.DataFrame(index=df.index)
    for side in ("home", "away"):
        club = g[f"{side}_club_id"].reindex(gid.values).values
        key = pd.MultiIndex.from_arrays([gid.values, club])
        row = xi.set_index(["game_id", "club_id"]).reindex(key)
        out[f"{side}_xi_log"] = np.log(row.xi_value.values.clip(1))
        out[f"{side}_xi_rel"] = np.log(row.xi_value.values.clip(1) / row.xi_usual.values.clip(1))
        out.loc[row.n_valued.values < 9, [f"{side}_xi_log", f"{side}_xi_rel"]] = np.nan
    out["xi_log_diff"] = out.home_xi_log - out.away_xi_log
    out["xi_rel_diff"] = out.home_xi_rel - out.away_xi_rel
    return out
