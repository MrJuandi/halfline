"""Modelo de goles tipo Dixon-Coles, re-ajustado cada semana con los partidos anteriores.

λ_local = exp(μ + ataque_local − defensa_visitante + ventaja_local), λ_visitante análogo.
- Objetivo: mezcla `goal_weight · goles + (1 − goal_weight) · xG` (Poisson de cuasi-verosimilitud,
  admite valores no enteros).
- Decaimiento temporal: peso exp(−ln 2 · días / half_life).
- Ridge (`alpha`) para que equipos con pocos partidos tiendan a la media; los ascendidos
  llevan además un indicador propio en su primera temporada.
- La corrección ρ de Dixon-Coles para marcadores bajos se aplica al convertir λ en
  probabilidades (`probs`), así que se ajusta sin re-entrenar.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from joblib import Parallel, delayed
from scipy.stats import poisson
from sklearn.linear_model import PoissonRegressor

from futdata.models.ratings import _newcomers

MAX_GOALS = 10


def _design(home, away, new_home, new_away, teams: dict[str, int]):
    """Dos filas por partido (goles del local, goles del visitante)."""
    n, t = len(home), len(teams)
    X = np.zeros((2 * n, 2 * t + 3))
    rows = np.arange(n)
    for side, (att, dfn, new_att, new_def) in enumerate(((home, away, new_home, new_away),
                                                          (away, home, new_away, new_home))):
        r = rows + side * n
        a = np.array([teams.get(x, -1) for x in att])
        d = np.array([teams.get(x, -1) for x in dfn])
        X[r[a >= 0], a[a >= 0]] = 1
        X[r[d >= 0], t + d[d >= 0]] = 1
        X[r, 2 * t] = 1 - side          # ventaja local
        X[r, 2 * t + 1] = new_att        # ataque de ascendido
        X[r, 2 * t + 2] = new_def        # defensa de ascendido
    return X


def _fit_predict(train: pd.DataFrame, test: pd.DataFrame, goal_weight: float, half_life: float,
                 alpha: float) -> np.ndarray:
    ref = test.kickoff.min()
    days = (ref - train.kickoff).dt.total_seconds() / 86400
    w = np.exp(-np.log(2) * days / half_life)
    keep = w > 1e-3
    train, w = train[keep], w[keep].values
    teams = {t: i for i, t in enumerate(pd.unique(np.r_[train.home.values, train.away.values]))}
    X = _design(train.home.values, train.away.values, train.new_home.values, train.new_away.values, teams)
    xg_h = train.home_xg.fillna(train.home_goals).values
    xg_a = train.away_xg.fillna(train.away_goals).values
    y = np.r_[goal_weight * train.home_goals + (1 - goal_weight) * xg_h,
              goal_weight * train.away_goals + (1 - goal_weight) * xg_a]
    model = PoissonRegressor(alpha=alpha, max_iter=300).fit(X, y, sample_weight=np.r_[w, w])
    Xt = _design(test.home.values, test.away.values, test.new_home.values, test.new_away.values, teams)
    lam = model.predict(Xt)
    return lam.reshape(2, -1).T  # (n, 2): λ local, λ visitante


def lambdas(df: pd.DataFrame, predict: pd.Series, goal_weight: float = 0.5,
            half_life: float = 180, alpha: float = 1e-3, n_jobs: int = -1) -> pd.DataFrame:
    """λ de cada partido marcado en `predict`, entrenando solo con partidos de semanas anteriores."""
    df = df.copy()
    new = _newcomers(df)
    df["new_home"] = [float((l, s, t) in new) for l, s, t in zip(df.league, df.season, df.home)]
    df["new_away"] = [float((l, s, t) in new) for l, s, t in zip(df.league, df.season, df.away)]
    df["week"] = df.kickoff.dt.tz_localize(None).dt.to_period("W-MON").dt.start_time.dt.tz_localize("UTC")
    jobs = []
    for (league, week), test in df[predict].groupby(["league", "week"]):
        train = df[(df.league == league) & (df.kickoff < week)]
        jobs.append((test.index, train, test))
    results = Parallel(n_jobs=n_jobs)(
        delayed(_fit_predict)(tr, te, goal_weight, half_life, alpha) for _, tr, te in jobs)
    out = pd.DataFrame(index=df.index[predict], columns=["lam_home", "lam_away"], dtype=float)
    for (idx, _, _), lam in zip(jobs, results):
        out.loc[idx] = lam
    return out


def probs(lam: pd.DataFrame, rho: float = 0.0, draw_inflation: float = 0.0) -> pd.DataFrame:
    """λ -> P(local, empate, visitante) y P(más de 2,5) con la corrección ρ de Dixon-Coles.

    `draw_inflation` (θ) multiplica por 1 + θ la diagonal (marcadores de empate) antes de normalizar:
    equivale a mezclar el modelo con su propia distribución de empates (Poisson inflado en la diagonal,
    Karlis y Ntzoufras 2003). Sube más el empate donde ya es probable, es decir, en partidos igualados.
    """
    g = np.arange(MAX_GOALS + 1)
    ph = poisson.pmf(g[None, :], lam.lam_home.values[:, None])
    pa = poisson.pmf(g[None, :], lam.lam_away.values[:, None])
    m = ph[:, :, None] * pa[:, None, :]  # (n, local, visitante)
    lh, la = lam.lam_home.values, lam.lam_away.values
    m[:, 0, 0] *= 1 - lh * la * rho
    m[:, 0, 1] *= 1 + lh * rho
    m[:, 1, 0] *= 1 + la * rho
    m[:, 1, 1] *= 1 - rho
    m[:, g, g] *= 1 + draw_inflation
    m /= m.sum(axis=(1, 2), keepdims=True)
    total = g[:, None] + g[None, :]
    return pd.DataFrame({
        "p_home": (m * (g[:, None] > g[None, :])).sum(axis=(1, 2)),
        "p_draw": (m * (g[:, None] == g[None, :])).sum(axis=(1, 2)),
        "p_away": (m * (g[:, None] < g[None, :])).sum(axis=(1, 2)),
        "p_over": (m * (total > 2.5)).sum(axis=(1, 2)),
    }, index=lam.index)
