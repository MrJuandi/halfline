"""Ratings secuenciales: el valor de cada partido se calcula ANTES de usar su resultado.

- elo(): Elo con margen de goles (elo_pass() devuelve también los ratings finales). `xg_weight` mezcla el resultado real con el resultado
  "merecido" según el xG (puntos esperados si los goles fueran Poisson(xG)).
  Los equipos nuevos en una liga (ascendidos) empiezan en `start_new`. Con `squad` (log del valor de
  plantilla por (liga, temporada, equipo), futdata.models.squads), cada ascendido se re-inicia en su
  primer partido de la temporada en (1 − value_weight)·start_new + value_weight·(rating que predice su
  valor), con la recta rating ~ log(valor) ajustada en ese momento sobre los demás equipos de su liga.
- pi_ratings(): Constantinou y Fenton (2013). Rating en casa y fuera por equipo, actualizado
  con el error en diferencia de goles (o de xG si `xg_weight` > 0).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import poisson

GOALS = np.arange(11)


def xg_points(xg_home: float, xg_away: float) -> float:
    """P(gana local) + 0,5 P(empate) si los goles fueran Poisson(xG)."""
    ph, pa = poisson.pmf(GOALS, xg_home), poisson.pmf(GOALS, xg_away)
    m = np.outer(ph, pa)
    return np.tril(m, -1).sum() + 0.5 * np.trace(m)


def _newcomers(df: pd.DataFrame) -> set[tuple[str, int, str]]:
    """(liga, temporada, equipo) de equipos que no estaban en esa liga la temporada anterior."""
    teams = pd.concat([df[["league", "season", "home"]].rename(columns={"home": "team"}),
                       df[["league", "season", "away"]].rename(columns={"away": "team"})]).drop_duplicates()
    first = teams.season.min()
    present = set(map(tuple, teams[["league", "season", "team"]].values))
    return {(lg, s, t) for lg, s, t in present if s > first and (lg, s - 1, t) not in present}


def elo(df: pd.DataFrame, k: float = 20, home: float = 60, start: float = 1500,
        start_new: float = 1500, xg_weight: float = 0.0, squad: dict | None = None,
        value_weight: float = 0.0) -> pd.Series:
    """Diferencia de Elo (local − visitante + ventaja local) antes de cada partido."""
    return elo_pass(df, k, home, start, start_new, xg_weight, squad, value_weight)[0]


def _value_start(ratings: dict[str, float], rivals: list[str], log_value: float | None,
                 squad: dict, league: str, season: int) -> float | None:
    """Rating que corresponde a `log_value` según la recta rating ~ log(valor) de `rivals`."""
    pts = [(squad.get((league, season, t)), ratings[t]) for t in rivals if t in ratings]
    pts = np.array([p for p in pts if p[0] is not None and np.isfinite(p[0])])
    if log_value is None or not np.isfinite(log_value) or len(pts) < 5:
        return None
    slope, intercept = np.polyfit(pts[:, 0], pts[:, 1], 1)
    return intercept + slope * log_value


def elo_pass(df: pd.DataFrame, k: float = 20, home: float = 60, start: float = 1500,
             start_new: float = 1500, xg_weight: float = 0.0, squad: dict | None = None,
             value_weight: float = 0.0) -> tuple[pd.Series, dict[str, float]]:
    """Como elo(), y además el rating de cada equipo tras el último partido de `df`."""
    new = _newcomers(df)
    teams = (pd.concat([df[["league", "season", "home"]].set_axis(["league", "season", "team"], axis=1),
                        df[["league", "season", "away"]].set_axis(["league", "season", "team"], axis=1)])
             .drop_duplicates().groupby(["league", "season"]).team.apply(list).to_dict()) if squad else {}
    ratings: dict[str, float] = {}
    started: set[tuple[str, int, str]] = set()
    out = np.empty(len(df))
    for i, m in enumerate(df.itertuples()):
        for team in (m.home, m.away):
            key = (m.league, m.season, team)
            if squad is not None and key in new and key not in started:
                started.add(key)  # ascendido: se re-inicia aunque ya hubiera estado en la liga
                rivals = [t for t in teams[(m.league, m.season)] if (m.league, m.season, t) not in new]
                pred = _value_start(ratings, rivals, squad.get(key), squad, m.league, m.season)
                ratings[team] = start_new if pred is None else \
                    (1 - value_weight) * start_new + value_weight * pred
            elif team not in ratings:
                ratings[team] = start_new if key in new else start
        rh, ra = ratings[m.home], ratings[m.away]
        out[i] = rh - ra + home
        expected = 1 / (1 + 10 ** (-(rh - ra + home) / 400))
        score = 1.0 if m.home_goals > m.away_goals else 0.5 if m.home_goals == m.away_goals else 0.0
        if xg_weight and not np.isnan(m.home_xg):
            score = (1 - xg_weight) * score + xg_weight * xg_points(m.home_xg, m.away_xg)
        margin = np.log1p(abs(m.home_goals - m.away_goals)) + 1
        delta = k * margin * (score - expected)
        ratings[m.home], ratings[m.away] = rh + delta, ra - delta
    return pd.Series(out, index=df.index), ratings


def pi_ratings(df: pd.DataFrame, lam: float = 0.035, gamma: float = 0.7, c: float = 3.0,
               xg_weight: float = 0.0) -> pd.DataFrame:
    """Diferencia de goles esperada según pi-ratings antes de cada partido (columna pi_gd)."""
    home_r: dict[str, float] = {}
    away_r: dict[str, float] = {}

    def expected_gd(r: float) -> float:
        return np.sign(r) * (10 ** (abs(r) / c) - 1)

    out = np.empty(len(df))
    for i, m in enumerate(df.itertuples()):
        hh, ha = home_r.get(m.home, 0.0), away_r.get(m.home, 0.0)
        ah, aa = home_r.get(m.away, 0.0), away_r.get(m.away, 0.0)
        exp_h, exp_a = expected_gd(hh), expected_gd(aa)
        out[i] = exp_h - exp_a
        gd = m.home_goals - m.away_goals
        if xg_weight and not np.isnan(m.home_xg):
            gd = (1 - xg_weight) * gd + xg_weight * (m.home_xg - m.away_xg)
        err = abs(gd - (exp_h - exp_a))
        psi = c * np.log10(1 + err)
        psi_h = psi if gd > exp_h - exp_a else -psi
        psi_a = -psi_h
        home_r[m.home] = hh + psi_h * lam
        away_r[m.home] = ha + (home_r[m.home] - hh) * gamma
        away_r[m.away] = aa + psi_a * lam
        home_r[m.away] = ah + (away_r[m.away] - aa) * gamma
    return pd.Series(out, index=df.index)
