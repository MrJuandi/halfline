"""Valor de plantilla (Transfermarkt) de cada equipo al empezar cada temporada.

Fecha de corte: la víspera del primer partido de la liga en esa temporada. Para cada jugador se
toma su última valoración anterior al corte y su club en ese momento: el destino de su último
traspaso (incluye cesiones) si es posterior a esa valoración, y si no, el club de la valoración.
Se descartan jugadores sin valorar en los 18 meses anteriores al corte (retirados o fuera del radar).

squad_value = suma de los `TOP` jugadores más valiosos (para que canteranos y cedidos sin valorar
no muevan la cifra). Sin valor (NaN) si hay menos de MIN_PLAYERS jugadores: pasa con los ascendidos
de 2026/27, porque el dataset se congeló (6/7/2026) antes de rastrear sus plantillas.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from futdata.models.lineups import TM, _games, club_ids

TOP = 25
STALE = pd.Timedelta(days=548)
MIN_PLAYERS = 18  # con menos, el dataset no tiene la plantilla (clubes no rastreados aún)


def _club_at(valuations: pd.DataFrame, transfers: pd.DataFrame, cut: pd.Timestamp) -> pd.DataFrame:
    """Una fila por jugador: club y valor a fecha `cut` (solo datos anteriores al corte)."""
    v = valuations[valuations.date < cut].drop_duplicates("player_id", keep="last")
    v = v[v.date >= cut - STALE]
    t = transfers[transfers.transfer_date < cut].drop_duplicates("player_id", keep="last")
    v = v.merge(t[["player_id", "transfer_date", "to_club_id"]], on="player_id", how="left")
    moved = v.transfer_date.notna() & (v.transfer_date > v.date)
    v["club_id"] = np.where(moved, v.to_club_id, v.current_club_id)
    return v[["player_id", "club_id", "market_value_in_eur"]]


def values(df: pd.DataFrame) -> pd.DataFrame:
    """(league, season, team) -> squad_value (€) y n_players, al corte de cada liga-temporada."""
    games = _games()
    clubs = club_ids(df, games)
    val = (pd.read_csv(TM / "player_valuations.csv.gz", parse_dates=["date"],
                       usecols=["player_id", "date", "market_value_in_eur", "current_club_id"])
           .sort_values(["date", "player_id"]))
    tr = (pd.read_csv(TM / "transfers.csv.gz", parse_dates=["transfer_date"],
                      usecols=["player_id", "transfer_date", "to_club_id"])
          .sort_values(["transfer_date", "player_id"]))
    teams = pd.concat([df[["league", "season", "home", "date"]].rename(columns={"home": "team"}),
                       df[["league", "season", "away", "date"]].rename(columns={"away": "team"})])
    rows = []
    for (league, season), g in teams.groupby(["league", "season"]):
        squad = _club_at(val, tr, pd.Timestamp(g.date.min()) - pd.Timedelta(days=1))
        for team in g.team.unique():
            club = clubs.get((league, team))
            mv = squad.loc[squad.club_id == club, "market_value_in_eur"].nlargest(TOP) if club is not None \
                else pd.Series(dtype=float)
            rows.append({"league": league, "season": season, "team": team,
                         "squad_value": mv.sum() if len(mv) >= MIN_PLAYERS else np.nan, "n_players": len(mv)})
    return pd.DataFrame(rows)
