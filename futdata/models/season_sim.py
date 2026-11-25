"""Simulación de Monte Carlo del resto de una temporada de liga.

Prototipo. Para cada liga, desde una fecha de corte y usando solo partidos anteriores:
  1. Tabla real + partidos que faltan (todos contra todos, ida y vuelta, menos los jugados).
  2. Fuerza de cada equipo = Elo ajustado + error de estimación N(0, sigma0²) + paseo aleatorio
     (sigma_w por raíz de semana). El error se sortea una vez por simulación: es lo que hace que los
     partidos de un mismo equipo estén correlacionados y que la tabla final no salga demasiado segura.
  3. Resultado 1X2 con la capa logística del Elo; marcador con Dixon-Coles condicionado a ese
     resultado (el Elo acierta algo más el 1X2, pero no da goles para los desempates).
  4. Clasificación con los desempates de la liga.

Aproximaciones: no hay fechas para todo el calendario, así que cada partido que falta cae en un momento
al azar hasta final de temporada; sin sanciones de puntos; el partido de desempate de la Serie A
(título y descenso) se resuelve por enfrentamientos directos, y lo que siga empatado, al azar.

Uso:
  python -m futdata.models.season_sim             → data/processed/season_sim.json
  python -m futdata.models.season_sim --backtest  → data/processed/season_sim_backtest.json
"""
from __future__ import annotations

import argparse
import itertools
import json

import numpy as np
import pandas as pd
from scipy.stats import poisson

from futdata.common import LEAGUES
from futdata.matches import PROCESSED
from futdata.models import data, evaluate, goals, ratings

H2H_LEAGUES = {"SP1", "I1"}  # desempate por enfrentamientos directos antes que por goles
DIRECT_DOWN = {"SP1": 3, "E0": 3, "I1": 3, "D1": 2, "F1": 2}  # D1 y F1: el 16.º juega promoción
WALK_STEPS = 10
G = goals.MAX_GOALS + 1


# ---------------------------------------------------------------- preparación

def remaining_fixtures(played: pd.DataFrame, teams: list[str]) -> list[tuple[str, str]]:
    """Pares (local, visitante) del todos contra todos que no están en `played`."""
    done = set(zip(played.home, played.away))
    return [p for p in itertools.permutations(teams, 2) if p not in done]


def score_cdfs(lam: np.ndarray, rho: float) -> np.ndarray:
    """(n, 3, G²): distribución acumulada del marcador de cada partido dado el 1X2."""
    g = np.arange(G)
    m = poisson.pmf(g[None], lam[:, :1])[:, :, None] * poisson.pmf(g[None], lam[:, 1:])[:, None, :]
    lh, la = lam[:, 0], lam[:, 1]
    m[:, 0, 0] *= 1 - lh * la * rho
    m[:, 0, 1] *= 1 + lh * rho
    m[:, 1, 0] *= 1 + la * rho
    m[:, 1, 1] *= 1 - rho
    masks = [g[:, None] > g[None], g[:, None] == g[None], g[:, None] < g[None]]
    c = np.stack([(m * k).reshape(len(lam), -1) for k in masks], axis=1).cumsum(axis=2)
    return c / c[:, :, -1:]


def prepare(df: pd.DataFrame, league: str, season: int, cutoff: pd.Timestamp, params: dict) -> dict:
    """Todo lo que la simulación necesita, calculado solo con partidos con inicio < cutoff."""
    lg = df[df.league == league]
    teams = sorted(set(lg[lg.season == season].home) | set(lg[lg.season == season].away))
    hist = lg[lg.kickoff < cutoff].reset_index(drop=True)
    played = hist[hist.season == season]
    fx = pd.DataFrame(remaining_fixtures(played, teams), columns=["home", "away"])

    e, dc = params["Elo ajustado"], params["Dixon-Coles xG/goles"]
    prev = set(lg[lg.season == season - 1].home)
    new = {(league, season, t) for t in teams if t not in prev} | ratings._newcomers(hist)
    diff, rat = ratings.elo_pass(hist, k=e["k"], home=e["home"], start_new=e["start_new"],
                                 xg_weight=e["xg_weight"])
    r = np.array([rat.get(t, e["start_new"]) for t in teams])

    # La capa 1X2 se entrena con las cinco ligas, como en evaluate
    past = df[(df.season >= evaluate.FIRST_PRED) & (df.season < season)]
    layer = evaluate.logistic().fit(params["_elo_diff"].loc[past.index].to_frame("r"), past.result)

    if len(fx):
        h = hist.assign(new_home=[float((league, s, t) in new) for s, t in zip(hist.season, hist.home)],
                        new_away=[float((league, s, t) in new) for s, t in zip(hist.season, hist.away)])
        test = fx.assign(kickoff=cutoff,
                         new_home=[float((league, season, t) in new) for t in fx.home],
                         new_away=[float((league, season, t) in new) for t in fx.away])
        lam = goals._fit_predict(h, test, dc["goal_weight"], dc["half_life"], dc["alpha"])
        cdfs = score_cdfs(np.clip(lam, 0.05, 6), dc["rho"])
    else:
        cdfs = np.empty((0, 3, G * G))
    ix = {t: i for i, t in enumerate(teams)}
    n = len(teams)
    pts, gd, gf, h2h_p, h2h_g = (np.zeros(s) for s in ((n,), (n,), (n,), (n, n), (n, n)))
    for m in played.itertuples():
        i, j, d = ix[m.home], ix[m.away], m.home_goals - m.away_goals
        pi, pj = (3, 0) if d > 0 else (1, 1) if d == 0 else (0, 3)
        for a, b, p, gg, f in ((i, j, pi, d, m.home_goals), (j, i, pj, -d, m.away_goals)):
            pts[a] += p; gd[a] += gg; gf[a] += f; h2h_p[a, b] += p; h2h_g[a, b] += gg
    end = pd.Timestamp(f"{season + 1}-05-25", tz="UTC")
    return {"league": league, "season": season, "teams": teams, "r": r, "home_adv": e["home"],
            "layer": layer, "fx": [(ix[a], ix[b]) for a, b in zip(fx.home, fx.away)], "cdfs": cdfs,
            "pts": pts, "gd": gd, "gf": gf, "h2h_p": h2h_p, "h2h_g": h2h_g,
            "played": len(played), "weeks": max((end - cutoff).days / 7, 0.0)}


# ---------------------------------------------------------------- simulación

def rank(league: str, pts, gd, gf, h2h_p, h2h_g, rng) -> np.ndarray:
    """Posición (1 = primero) de cada equipo en cada simulación."""
    if league in H2H_LEAGUES:
        eq = pts[:, :, None] == pts[:, None, :]  # minitabla entre los empatados a puntos
        keys = [(h2h_p * eq).sum(2), (h2h_g * eq).sum(2), gd, gf]
    else:
        keys = [gd, gf]
    order = np.lexsort([rng.random(pts.shape)] + [-k for k in reversed(keys)] + [-pts], axis=1)
    pos = np.empty_like(order)
    np.put_along_axis(pos, order, np.arange(1, pts.shape[1] + 1)[None], axis=1)
    return pos


def simulate(st: dict, n: int = 20000, sigma0: float = 0.0, sigma_w: float = 0.0, seed: int = 0,
             equal: bool = False) -> dict:
    """Simula el resto de la temporada. `equal`: todos los equipos con la misma fuerza (referencia)."""
    rng = np.random.default_rng(seed)
    T = len(st["teams"])
    pts, gd, gf = (np.tile(st[k], (n, 1)) for k in ("pts", "gd", "gf"))
    h2h_p = np.tile(st["h2h_p"], (n, 1, 1)).astype(np.float32)
    h2h_g = np.tile(st["h2h_g"], (n, 1, 1)).astype(np.float32)
    base = np.full(T, 1500.0) if equal else st["r"]
    e0 = rng.normal(0, sigma0, (n, T)) if sigma0 else np.zeros((n, T))
    step = sigma_w * np.sqrt(st["weeks"] / WALK_STEPS)
    when = np.sort(rng.integers(0, WALK_STEPS, len(st["fx"])))
    order = rng.permutation(len(st["fx"]))
    now = -1
    for f, w in zip(order, when):
        while now < w:
            now += 1
            if step:
                e0 = e0 + rng.normal(0, step, (n, T))
        i, j = st["fx"][f]
        r = base[i] - base[j] + st["home_adv"] + e0[:, i] - e0[:, j]
        if np.ptp(r):
            p = st["layer"].predict_proba(pd.DataFrame({"r": r}))
        else:
            p = np.repeat(st["layer"].predict_proba(pd.DataFrame({"r": r[:1]})), n, axis=0)
        u = rng.random(n)
        res = (u > p[:, 0]).astype(int) + (u > p[:, 0] + p[:, 1])
        v = rng.random(n)
        cell = np.empty(n, dtype=int)
        for k in range(3):
            s = res == k
            cell[s] = np.searchsorted(st["cdfs"][f, k], v[s])
        cell = np.minimum(cell, G * G - 1)
        hg, ag = cell // G, cell % G
        d = hg - ag
        ph, pa = np.where(res == 0, 3, res == 1), np.where(res == 2, 3, res == 1)
        pts[:, i] += ph; pts[:, j] += pa
        gd[:, i] += d; gd[:, j] -= d
        gf[:, i] += hg; gf[:, j] += ag
        h2h_p[:, i, j] += ph; h2h_p[:, j, i] += pa
        h2h_g[:, i, j] += d; h2h_g[:, j, i] -= d
    return {"pts": pts, "pos": rank(st["league"], pts, gd, gf, h2h_p, h2h_g, rng)}


def events(pos: np.ndarray, league: str) -> dict[str, np.ndarray]:
    T = pos.shape[-1]
    return {"title": pos == 1, "top4": pos <= 4, "down": pos > T - DIRECT_DOWN[league]}


# ---------------------------------------------------------------- backtest

def crps(sample: np.ndarray, y: float) -> float:
    """CRPS de una muestra frente a un valor observado (menor es mejor)."""
    s = np.sort(sample)
    n = len(s)
    return float(np.abs(s - y).mean() - ((2 * np.arange(1, n + 1) - n - 1) * s).sum() / n ** 2)


def load_inputs() -> tuple[pd.DataFrame, dict]:
    df = data.load()
    params = json.loads((PROCESSED / "model_report.json").read_bytes())["elegidos"]
    e = params["Elo ajustado"]
    params["_elo_diff"] = ratings.elo(df, k=e["k"], home=e["home"], start_new=e["start_new"],
                                      xg_weight=e["xg_weight"])
    return df, params


def cutoffs(df: pd.DataFrame, league: str, season: int, fractions) -> dict[float, pd.Timestamp]:
    k = df[(df.league == league) & (df.season == season)].kickoff.sort_values()
    return {f: k.iloc[int(f * len(k))] for f in fractions}


def backtest(df, params, seasons, configs: dict[str, dict], fractions=(0, 0.25, 0.5, 0.75),
             n: int = 4000) -> pd.DataFrame:
    """Una fila por (config, liga, temporada, fracción, equipo) con probabilidades y lo que pasó."""
    rows = []
    for season, league in itertools.product(seasons, LEAGUES):
        full = prepare(df, league, season, pd.Timestamp("2100-01-01", tz="UTC"), params)
        assert not full["fx"], (league, season, len(full["fx"]))
        real = simulate(full, n=1)
        ev_real = {k: v[0] for k, v in events(real["pos"], league).items()}
        for frac, cut in cutoffs(df, league, season, fractions).items():
            st = prepare(df, league, season, cut, params)
            for name, cfg in configs.items():
                sim = simulate(st, n=n, seed=1, **cfg)
                ev = events(sim["pos"], league)
                for t, team in enumerate(st["teams"]):
                    x, y = sim["pts"][:, t], real["pts"][0, t]
                    lo, hi = np.quantile(x, [0.1, 0.9])
                    rows.append({"config": name, "league": league, "season": season, "frac": frac,
                                 "team": team, "y": y, "mean": x.mean(), "crps": crps(x, y),
                                 "in80": lo <= y <= hi,
                                 # PIT a mitad de empate: cobertura sin el sesgo de puntos enteros
                                 "pit": (x < y).mean() + 0.5 * (x == y).mean(),
                                 **{f"p_{k}": v[:, t].mean() for k, v in ev.items()},
                                 **{f"y_{k}": bool(ev_real[k][t]) for k in ev}})
    return pd.DataFrame(rows)


def summary(bt: pd.DataFrame, by=("config",)) -> pd.DataFrame:
    out = bt.groupby(list(by)).apply(lambda g: pd.Series({
        "crps": g.crps.mean(), "mae": (g["mean"] - g.y).abs().mean(),
        "cob80": g.pit.between(0.1, 0.9).mean(),
        **{f"brier_{k}": ((g[f"p_{k}"] - g[f"y_{k}"]) ** 2).mean() for k in ("title", "top4", "down")},
    }), include_groups=False)
    return out


def calibration(bt: pd.DataFrame, bins=(0, .05, .2, .4, .6, .8, .95, 1.0001)) -> list[dict]:
    p = np.concatenate([bt[f"p_{k}"] for k in ("title", "top4", "down")])
    y = np.concatenate([bt[f"y_{k}"] for k in ("title", "top4", "down")]).astype(float)
    b = np.digitize(p, bins) - 1
    return [{"de": bins[i], "a": min(bins[i + 1], 1), "n": int((b == i).sum()),
             "previsto": float(p[b == i].mean()), "real": float(y[b == i].mean())}
            for i in range(len(bins) - 1) if (b == i).any()]


# Elegidos en las temporadas de ajuste (2023/24 y 2024/25); ver run_backtest
DEFAULT = {"sigma0": 0.0, "sigma_w": 8.0}
TUNE, TEST = (2023, 2024), (2025,)


def run_backtest(n: int = 4000) -> dict:
    df, params = load_inputs()
    grid = {f"s0={a},sw={b}": {"sigma0": a, "sigma_w": b}
            for a, b in itertools.product((0, 25, 50, 75, 100), (0, 8, 16))}
    tune = backtest(df, params, TUNE, grid, n=n)
    best = summary(tune).crps.idxmin()
    test = backtest(df, params, TEST, {"fija": {}, "elegida": grid[best], "iguales": {"equal": True}}, n=n)
    return {"tune": tune, "test": test, "best": best, "cfg": grid[best]}


def current(n: int = 20000, cfg: dict | None = None, season: int | None = None) -> dict:
    df, params = load_inputs()
    season = int(df.season.max()) if season is None else season
    cut = df.kickoff.max() + pd.Timedelta(minutes=1)
    out = {"season": season, "data_through": str(df.date.max().date()), "n": n, "leagues": {}}
    for league in LEAGUES:
        st = prepare(df, league, season, cut, params)
        sim = simulate(st, n=n, **(cfg or DEFAULT))
        ev = events(sim["pos"], league)
        rows = [{"team": t, "pts": int(st["pts"][i]), "pts_mean": float(sim["pts"][:, i].mean()),
                 "pts_p10": float(np.quantile(sim["pts"][:, i], .1)),
                 "pts_p90": float(np.quantile(sim["pts"][:, i], .9)),
                 **{k: float(v[:, i].mean()) for k, v in ev.items()},
                 "pos": [float((sim["pos"][:, i] == k).mean()) for k in range(1, len(st["teams"]) + 1)]}
                for i, t in enumerate(st["teams"])]
        out["leagues"][league] = {"played": st["played"], "remaining": len(st["fx"]),
                                  "rows": sorted(rows, key=lambda x: -x["pts_mean"])}
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--backtest", action="store_true")
    ap.add_argument("-n", type=int, default=None)
    ap.add_argument("--out", default=None, help="ruta de salida (por defecto, data/processed)")
    a = ap.parse_args()
    if a.backtest:
        r = run_backtest(a.n or 4000)
        res = {"elegida": r["cfg"], "ajuste": summary(r["tune"]).reset_index().to_dict("records"),
               "test": summary(r["test"]).reset_index().to_dict("records"),
               "test_por_momento": summary(r["test"], ("config", "frac")).reset_index().to_dict("records"),
               "calibracion_test": {c: calibration(g) for c, g in r["test"].groupby("config")}}
        path = a.out or PROCESSED / "season_sim_backtest.json"
    else:
        res, path = current(a.n or 20000), a.out or PROCESSED / "season_sim.json"
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(res, fh, ensure_ascii=False, indent=1)
    print(path)


if __name__ == "__main__":
    main()
