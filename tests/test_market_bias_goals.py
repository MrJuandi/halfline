"""Liquidación del hándicap asiático y reglas de market_bias_goals. No necesitan datos."""
import numpy as np
import pandas as pd
import pytest

from futdata.models.market_bias_goals import ah_profit, ah_split, odds_of, outcomes, picks, target

# (línea del que apuesta, sus goles − los del rival) -> (ganada, devuelta, perdida)
CASES = [
    # líneas de .5: nunca hay devolución
    (-0.5, 1, (1, 0, 0)), (-0.5, 0, (0, 0, 1)), (0.5, 0, (1, 0, 0)), (0.5, -1, (0, 0, 1)),
    (-1.5, 1, (0, 0, 1)), (-1.5, 2, (1, 0, 0)),
    # líneas enteras: push = devolución
    (0, 0, (0, 1, 0)), (0, 1, (1, 0, 0)), (0, -1, (0, 0, 1)),
    (-1, 1, (0, 1, 0)), (-1, 2, (1, 0, 0)), (-1, 0, (0, 0, 1)),
    (1, -1, (0, 1, 0)), (2, -2, (0, 1, 0)), (2, -1, (1, 0, 0)),
    # líneas de cuarto: mitad a cada línea vecina
    (-0.25, 0, (0, 0.5, 0.5)), (-0.25, 1, (1, 0, 0)), (-0.25, -1, (0, 0, 1)),
    (0.25, 0, (0.5, 0.5, 0)), (0.25, -1, (0, 0, 1)),
    (-0.75, 1, (0.5, 0.5, 0)), (-0.75, 2, (1, 0, 0)), (-0.75, 0, (0, 0, 1)),
    (0.75, -1, (0, 0.5, 0.5)), (0.75, 0, (1, 0, 0)),
    (-1.25, 1, (0, 0.5, 0.5)), (-1.75, 2, (0.5, 0.5, 0)), (1.25, -1, (0.5, 0.5, 0)),
]


@pytest.mark.parametrize("line,diff,expected", CASES)
def test_ah_split_cases(line, diff, expected):
    assert np.allclose(np.array(ah_split(line, diff), float), expected)


def test_ah_split_vectorised_and_sums_to_one():
    lines = np.repeat(np.arange(-3, 3.25, 0.25), 9)
    diffs = np.tile(np.arange(-4, 5), len(lines) // 9)
    win, push, lose = ah_split(lines, diffs)
    assert np.allclose(win + push + lose, 1)
    assert set(np.unique(win)) <= {0, 0.5, 1}


def test_ah_both_sides_mirror():
    """Lo que gana el local lo pierde el visitante con la línea contraria."""
    lines = np.repeat(np.arange(-2, 2.25, 0.25), 7)
    diffs = np.tile(np.arange(-3, 4), len(lines) // 7)
    wh, ph, lh = ah_split(lines, diffs)
    wa, pa, la = ah_split(-lines, -diffs)
    assert np.allclose(wh, la) and np.allclose(lh, wa) and np.allclose(ph, pa)


def test_ah_profit():
    assert ah_profit(-0.75, 1, 1.90) == pytest.approx(0.45)   # media ganada, media devuelta
    assert ah_profit(-0.25, 0, 1.90) == pytest.approx(-0.5)   # media perdida, media devuelta
    assert ah_profit(-1, 1, 1.90) == pytest.approx(0)         # push
    assert ah_profit(-0.5, 1, 1.90) == pytest.approx(0.9)
    assert ah_profit(-0.5, 0, 1.90) == pytest.approx(-1)


def _df(line, home, away):
    return pd.DataFrame({"ah_line": line, "diff": np.subtract(home, away),
                         "over": (np.add(home, away) > 2.5).astype(int)})


def test_target_is_binary_with_unrefunded_weight():
    df = _df([-0.75, -0.75, -1.0, -0.25, 0.5], [2, 1, 1, 0, 0], [1, 0, 0, 0, 1])
    y, w = target(df, "ah")
    # diff 1 a −0,75: medio ganado → y=1, peso 0,5 ; push en −1: peso 0 ; medio perdido a −0,25: y=0, peso 0,5
    assert list(w) == [0.5, 0.5, 0, 0.5, 1]
    assert list(y[w > 0]) == [1, 1, 0, 0]


def test_ou_outcomes():
    df = _df([0, 0], [2, 1], [1, 1])
    W, L = outcomes(df, "ou")
    assert W.tolist() == [[1, 0], [0, 1]] and L.tolist() == [[0, 1], [1, 0]]


def test_odds_cleaning_and_betfair_commission():
    df = pd.DataFrame({"ah_mkt_0": [1.9, 1.82], "ah_mkt_1": [1.95, 4.10],   # 2ª fila sin margen: error
                       "ah_max_0": [2.6, 1.85], "ah_max_1": [2.0, 22.0],    # 2,6 > 1,25 × media
                       "ah_bfe_0": [2.0, 2.0], "ah_bfe_1": [2.0, 1.0]})
    mkt = odds_of(df, "ah", "mkt")
    assert np.isnan(mkt[1]).all() and not np.isnan(mkt[0]).any()
    mx = odds_of(df, "ah", "max")
    assert np.isnan(mx[0, 0]) and mx[0, 1] == 2.0 and np.isnan(mx[1]).all()
    bfe = odds_of(df, "ah", "bfe")
    assert bfe[0, 0] == pytest.approx(1.95) and np.isnan(bfe[1, 1])


def test_picks_rules():
    p = np.array([[0.62, 0.38], [0.45, 0.55], [0.50, 0.50]])
    odds = np.array([[1.55, 2.5], [2.30, 1.70], [2.10, 1.95]])
    assert list(picks("más", 0.6, p, odds)) == [0, -1, -1]
    assert list(picks("menos", 0.48, p, odds)) == [-1, 1, -1]
    assert list(picks("valor", 0.02, p, odds)) == [-1, 0, 0]  # 0,45 × 2,30 = 1,035 ; 0,5 × 2,1 = 1,05
    p_model = np.array([0.70, 0.40, np.nan])
    assert list(picks("DC diferencia", 0.04, p, odds, p_model=p_model)) == [0, 1, -1]
    assert list(picks("DC valor", 0.0, p, odds, p_model=p_model)) == [0, 1, -1]
    line = np.array([-1.5, 0.75, 0.0])
    assert list(picks("favorito", 0.75, p, odds, line=line)) == [0, 1, -1]
    assert list(picks("no favorito", 1.0, p, odds, line=line)) == [1, -1, -1]
