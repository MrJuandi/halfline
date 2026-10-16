"""Métodos para quitar el margen (futdata.models.margin) y reglas de market_bias. No necesitan datos."""
import numpy as np

from futdata.models.margin import fair, power, proportional, shin
from futdata.models.market_bias import picks

ODDS = np.array([[1.30, 5.50, 10.0], [2.60, 3.20, 2.90], [1.95, 3.60, 4.20]])


def test_methods_sum_to_one():
    for f in (proportional, shin, power):
        p = f(ODDS)
        assert np.allclose(p.sum(1), 1)
        assert (p > 0).all()


def test_shin_and_power_take_more_margin_from_longshots():
    """Frente al proporcional, Shin y potencia suben al favorito y bajan a la sorpresa."""
    prop = proportional(ODDS)
    for f in (shin, power):
        p = f(ODDS)
        assert p[0, 0] > prop[0, 0] and p[0, 2] < prop[0, 2]


def test_no_margin_leaves_probabilities_unchanged():
    fair = np.array([[0.5, 0.3, 0.2]])
    for f in (proportional, shin, power):
        assert np.allclose(f(1 / fair), fair, atol=1e-6)


def test_picks_rules():
    p = np.array([[0.7, 0.2, 0.1], [0.36, 0.30, 0.34]])
    assert list(picks("favorito", 0.65, p, None)) == [0, -1]
    assert list(picks("empate igualado", 0.1, p, None)) == [-1, 1]
    odds = np.array([[1.40, 5.0, 9.0], [2.9, 3.6, 2.9]])  # 0,30 × 3,6 = 1,08
    assert list(picks("valor Shin", 0.05, p, odds)) == [-1, 1]


def test_fair_is_power_and_nan_without_odds():
    odds = np.vstack([ODDS, [[2.0, np.nan, 3.0]], [[1.0, 3.0, 3.0]]])
    p = fair(odds)
    assert np.allclose(p[:3], power(ODDS))
    assert np.isnan(p[3:]).all()
