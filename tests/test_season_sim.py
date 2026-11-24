"""Tests del simulador de temporada con datos sintéticos (no necesitan data/)."""
import numpy as np
import pandas as pd
import pytest

from futdata.models import evaluate, goals
from futdata.models import season_sim as S


@pytest.fixture(scope="module")
def layer():
    rng = np.random.default_rng(0)
    r = rng.normal(40, 120, 6000)
    ph = 1 / (1 + 10 ** (-r / 400)) * 0.75
    u = rng.random(6000)
    y = np.where(u < ph, 0, np.where(u < ph + 0.25, 1, 2))
    return evaluate.logistic().fit(pd.DataFrame({"r": r}), y)


def state(layer, n_teams=4, league="E0", r=None, **over):
    teams = [f"T{i}" for i in range(n_teams)]
    fx = [(i, j) for i in range(n_teams) for j in range(n_teams) if i != j]
    lam = np.tile([1.5, 1.1], (len(fx), 1))
    z = np.zeros(n_teams)
    st = {"league": league, "season": 2025, "teams": teams, "r": np.full(n_teams, 1500.0) if r is None else r,
          "home_adv": 40.0, "layer": layer, "fx": fx, "cdfs": S.score_cdfs(lam, -0.1), "pts": z.copy(),
          "gd": z.copy(), "gf": z.copy(), "h2h_p": np.zeros((n_teams, n_teams)),
          "h2h_g": np.zeros((n_teams, n_teams)), "played": 0, "weeks": 30.0}
    return {**st, **over}


def test_remaining_fixtures():
    played = pd.DataFrame({"home": ["A", "B"], "away": ["B", "C"]})
    fx = S.remaining_fixtures(played, ["A", "B", "C"])
    assert len(fx) == 4 and ("A", "B") not in fx and ("B", "A") in fx


def test_score_cdfs_reproduce_dixon_coles():
    lam = np.array([[1.7, 0.9], [0.4, 2.3]])
    c = S.score_cdfs(lam, -0.1)
    pmf = np.diff(c, axis=2, prepend=0)
    p = goals.probs(pd.DataFrame(lam, columns=["lam_home", "lam_away"]), rho=-0.1)
    g = np.arange(S.G)
    over = ((g[:, None] + g[None]) > 2.5).ravel()
    got = sum(p[k].values * pmf[:, i][:, over].sum(1) for i, k in enumerate(("p_home", "p_draw", "p_away")))
    assert np.allclose(got, p.p_over.values)
    cells = np.arange(S.G ** 2)
    d = cells // S.G - cells % S.G
    assert np.allclose(pmf[:, 0][:, d <= 0], 0) and np.allclose(pmf[:, 1][:, d != 0], 0)


def test_simulated_points_match_layer(layer):
    st = state(layer, n_teams=2)
    sim = S.simulate(st, n=40000)
    p = layer.predict_proba(pd.DataFrame({"r": [40.0]}))[0]
    expected = (3 * p[0] + p[1]) + (3 * p[2] + p[1])
    assert sim["pts"][:, 0].mean() == pytest.approx(expected, abs=0.04)


def test_every_position_once_and_points_bounds(layer):
    st = state(layer, n_teams=6)
    sim = S.simulate(st, n=500, sigma0=50, sigma_w=8)
    assert (np.sort(sim["pos"], axis=1) == np.arange(1, 7)).all()
    assert (sim["pts"].sum(1) >= 2 * 30).all() and (sim["pts"].sum(1) <= 3 * 30).all()


def test_strength_noise_widens_and_is_reproducible(layer):
    st = state(layer, n_teams=8)
    a, b, c = (S.simulate(st, n=4000, sigma0=s, seed=3)["pts"] for s in (0, 100, 100))
    assert b.std(0).mean() > a.std(0).mean() * 1.1
    assert (b == c).all()


def test_input_state_not_modified(layer):
    st = state(layer)
    S.simulate(st, n=50, sigma0=20)
    assert (st["pts"] == 0).all() and (st["h2h_p"] == 0).all()


@pytest.mark.parametrize("league,first", [("SP1", 0), ("I1", 0), ("E0", 1), ("D1", 1), ("F1", 1)])
def test_tiebreak_rules(league, first):
    """0 y 1 empatan a puntos: 0 gana el directo, 1 tiene mejor diferencia de goles."""
    pts, gd, gf = np.array([[10., 10, 2]]), np.array([[3., 9, -12]]), np.array([[8., 12, 1]])
    hp, hg = np.zeros((1, 3, 3)), np.zeros((1, 3, 3))
    hp[0, 0, 1], hp[0, 1, 0], hg[0, 0, 1], hg[0, 1, 0] = 4, 1, 1, -1
    pos = S.rank(league, pts, gd, gf, hp, hg, np.random.default_rng(0))
    assert pos[0, first] == 1 and pos[0, 2] == 3


def test_h2h_mini_table_uses_only_tied_teams():
    """El 2 no está empatado: sus enfrentamientos no cuentan en el desempate entre 0 y 1."""
    pts, gd, gf = np.array([[10., 10, 4]]), np.zeros((1, 3)), np.zeros((1, 3))
    hp, hg = np.zeros((1, 3, 3)), np.zeros((1, 3, 3))
    hp[0, 0, 1], hp[0, 1, 0], hp[0, 1, 2] = 4, 1, 6
    assert S.rank("SP1", pts, gd, gf, hp, hg, np.random.default_rng(0))[0, 0] == 1


def test_season_over_is_deterministic(layer):
    st = state(layer, fx=[], cdfs=np.empty((0, 3, S.G ** 2)), pts=np.array([9., 7, 4, 1]))
    assert (S.simulate(st, n=20, sigma0=80)["pos"] == np.array([1, 2, 3, 4])).all()


def test_events_relegation_places():
    pos = np.arange(1, 19)[None]
    assert S.events(pos, "D1")["down"].sum() == 2
    assert S.events(np.arange(1, 21)[None], "SP1")["down"].sum() == 3


def test_crps():
    assert S.crps(np.array([5.0, 5.0]), 5.0) == 0
    assert S.crps(np.array([4.0]), 7.0) == 3
    assert S.crps(np.array([0.0, 2.0]), 1.0) == pytest.approx(0.5)
