"""Momentos y mercados formados de futdata.models.pm_horizons. No necesitan datos."""
import math

import numpy as np

from futdata.models.pm_horizons import formed, moment_ts

OPEN, KICKOFF = 1_000_000.0, 1_000_000.0 + 300 * 3600


def test_moments_after_open_and_before_kickoff():
    assert moment_ts("apertura", OPEN, KICKOFF) == OPEN
    assert moment_ts("ap+24h", OPEN, KICKOFF) == OPEN + 24 * 3600
    assert moment_ts("1d", OPEN, KICKOFF) == KICKOFF - 24 * 3600


def test_moments_never_use_last_hour_or_before_open():
    """Ni precios de la última hora (ni posteriores al inicio) ni anteriores a la apertura."""
    late_open = KICKOFF - 50 * 3600
    assert math.isnan(moment_ts("ap+72h", late_open, KICKOFF))  # caería después del inicio
    assert math.isnan(moment_ts("3d", late_open, KICKOFF))      # antes de que abriera
    assert moment_ts("1h", OPEN, KICKOFF) == KICKOFF - 3600


def test_formed_requires_prices_summing_close_to_one():
    raw = np.array([[0.5, 0.5, 0.5], [0.45, 0.28, 0.28], [0.40, 0.25, 0.30]])
    assert list(formed(raw)) == [False, True, False]
