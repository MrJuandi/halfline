"""Tests de los modelos: fuga temporal y coherencia de probabilidades (datos sintéticos)."""
import itertools

import numpy as np
import pandas as pd
from scipy.stats import poisson

from futdata.models import goals, ratings
from futdata.models.evaluate import logloss_rows, rps_rows


def _league(n_weeks=12, seed=0):
    """Liga de 4 equipos, dos partidos por semana."""
    rng = np.random.default_rng(seed)
    teams = ["A", "B", "C", "D"]
    rows = []
    for w in range(n_weeks):
        kickoff = pd.Timestamp("2023-08-05 15:00", tz="UTC") + pd.Timedelta(weeks=w)
        order = rng.permutation(teams)
        for h, a in ((order[0], order[1]), (order[2], order[3])):
            hg, ag = rng.poisson(1.5), rng.poisson(1.1)
            rows.append({"match_id": f"{w}{h}{a}", "league": "X", "season": 2023, "kickoff": kickoff,
                         "home": h, "away": a, "home_goals": hg, "away_goals": ag,
                         "home_xg": hg + 0.1, "away_xg": ag + 0.2})
    return pd.DataFrame(rows)


def test_goal_model_does_not_see_its_own_week():
    df = _league()
    pred = pd.Series(df.index >= len(df) - 2, index=df.index)  # última semana
    base = goals.lambdas(df, pred, n_jobs=1)
    changed = df.copy()
    changed.loc[pred, ["home_goals", "home_xg"]] = 9
    assert np.allclose(base.values, goals.lambdas(changed, pred, n_jobs=1).values)
    earlier = df.copy()
    earlier.loc[0, ["home_goals", "home_xg"]] = 9  # un partido anterior sí cuenta
    assert not np.allclose(base.values, goals.lambdas(earlier, pred, n_jobs=1).values)


def test_ratings_use_only_previous_matches():
    df = _league()
    changed = df.copy()
    changed.loc[10, ["home_goals", "home_xg"]] = 9
    for f in (ratings.elo, ratings.pi_ratings):
        a, b = f(df, xg_weight=0.5), f(changed, xg_weight=0.5)
        assert np.allclose(a[:11], b[:11])        # hasta el propio partido, idénticos
        assert not np.allclose(a[11:], b[11:])    # después sí cambia


def test_probabilities_are_coherent():
    lam = pd.DataFrame({"lam_home": [1.5, 0.4, 3.0], "lam_away": [1.1, 2.2, 0.3]})
    for rho in (-0.1, 0.0):
        p = goals.probs(lam, rho)
        assert np.allclose(p[["p_home", "p_draw", "p_away"]].sum(1), 1)
        assert ((p.p_over > 0) & (p.p_over < 1)).all()
    p0 = goals.probs(lam, 0.0)
    g = np.arange(11)
    draw = (poisson.pmf(g, 1.5) * poisson.pmf(g, 1.1)).sum()
    assert np.isclose(p0.p_draw[0], draw, atol=1e-6)
    assert goals.probs(lam, -0.1).p_draw[0] > p0.p_draw[0]  # ρ < 0 sube los empates


def test_metrics():
    y = np.array([0, 1, 2])
    perfect = np.eye(3)
    assert np.allclose(rps_rows(perfect, y), 0) and np.allclose(logloss_rows(perfect, y), 0)
    flat = np.full((3, 3), 1 / 3)
    assert np.allclose(logloss_rows(flat, y), np.log(3))
    assert rps_rows(np.array([[0, 0, 1.0]]), np.array([0]))[0] > rps_rows(np.array([[0, 1.0, 0]]), np.array([0]))[0]


def test_draw_inflation_raises_draws_and_stays_coherent():
    lam = pd.DataFrame({"lam_home": [1.2, 2.5], "lam_away": [1.1, 0.5]})
    base, infl = goals.probs(lam, -0.1), goals.probs(lam, -0.1, draw_inflation=0.2)
    assert np.allclose(infl[["p_home", "p_draw", "p_away"]].sum(1), 1)
    assert (infl.p_draw > base.p_draw).all()
    # sube más (en puntos) en el partido igualado que en el desequilibrado
    assert (infl.p_draw - base.p_draw)[0] > (infl.p_draw - base.p_draw)[1]
    assert np.allclose(goals.probs(lam, -0.1, 0.0).values, base.values)


def test_draw_layer_can_exceed_single_logistic():
    """Con |r| la capa multinomial puede dar más empate en partidos igualados que la de una variable."""
    from futdata.models.evaluate import DRAW_SETS, draw_features, logistic
    rng = np.random.default_rng(1)
    r = pd.Series(rng.normal(0, 150, 6000))
    p_draw = 0.36 * np.exp(-(r / 120) ** 2) + 0.12  # empates concentrados en r ≈ 0
    p_home = (1 - p_draw) / (1 + np.exp(-r / 150))
    u = rng.random(len(r))
    y = np.where(u < p_home, 0, np.where(u < p_home + p_draw, 1, 2))
    lam = pd.DataFrame({"lam_home": np.full(len(r), 1.4), "lam_away": np.full(len(r), 1.1)})
    X = draw_features(r, lam)
    one = logistic().fit(X[["r"]], y).predict_proba(X[["r"]])[:, 1]
    two = logistic().fit(X[DRAW_SETS["r, |r|"]], y).predict_proba(X[DRAW_SETS["r, |r|"]])[:, 1]
    close = r.abs().values < 30
    assert two[close].mean() > one[close].mean() + 0.05
    assert abs(two[close].mean() - (y[close] == 1).mean()) < 0.04


def _two_seasons():
    """Temporada 2022 con A, B, C, D, E, F; en 2023 baja F y sube G (rico) — liga de 6 equipos."""
    rows = []
    for season, teams in ((2022, list("ABCDEF")), (2023, list("ABCDEG"))):
        for w, (h, a) in enumerate(itertools.permutations(teams, 2)):
            strength = {"A": 3, "B": 2, "C": 1, "D": 0, "E": -1, "F": -2, "G": 2}
            hg, ag = max(0, 1 + strength[h] - strength[a]), max(0, 1 + strength[a] - strength[h])
            rows.append({"league": "X", "season": season, "home": h, "away": a, "home_goals": hg,
                         "away_goals": ag, "home_xg": np.nan, "away_xg": np.nan,
                         "kickoff": pd.Timestamp(f"{season}-08-01", tz="UTC") + pd.Timedelta(days=w)})
    return pd.DataFrame(rows)


def test_promoted_start_follows_squad_value():
    df = _two_seasons()
    value = {"A": 500, "B": 300, "C": 200, "D": 120, "E": 80, "F": 50}
    squad = {("X", 2023, t): np.log(v) for t, v in value.items()}
    first = df.index[(df.season == 2023) & ((df.home == "G") | (df.away == "G"))][0]

    def first_diff(v):
        squad[("X", 2023, "G")] = np.log(v)
        return ratings.elo(df, start_new=1400, squad=squad, value_weight=1).loc[first]

    rich, poor = first_diff(400), first_diff(30)
    sign = 1 if df.loc[first, "home"] == "G" else -1
    assert sign * (rich - poor) > 50   # plantilla cara -> empieza más arriba
    # value_weight = 0: rating fijo, se ignora el valor
    squad[("X", 2023, "G")] = np.log(400)
    a = ratings.elo(df, start_new=1400, squad=squad, value_weight=0).loc[first]
    squad[("X", 2023, "G")] = np.log(30)
    assert np.isclose(a, ratings.elo(df, start_new=1400, squad=squad, value_weight=0).loc[first])
    # sin valor de plantilla: se usa start_new
    squad.pop(("X", 2023, "G"))
    assert np.isclose(a, ratings.elo(df, start_new=1400, squad=squad, value_weight=1).loc[first])


def test_promoted_start_uses_only_previous_matches():
    df = _two_seasons()
    squad = {("X", 2023, t): np.log(v) for t, v in zip("ABCDEG", [500, 300, 200, 120, 80, 250])}
    changed = df.copy()
    later = df.index[df.season == 2023][5]
    changed.loc[later, "home_goals"] = 9
    a = ratings.elo(df, squad=squad, value_weight=1)
    b = ratings.elo(changed, squad=squad, value_weight=1)
    assert np.allclose(a[:later + 1], b[:later + 1]) and not np.allclose(a[later + 1:], b[later + 1:])
