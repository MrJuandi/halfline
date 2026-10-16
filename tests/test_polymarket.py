"""Tests del procesado de Polymarket (sin red)."""
import math

import pandas as pd

from futdata.polymarket import _price_at, fd_snapshot_time


def test_fd_snapshot_time():
    sat = pd.Timestamp("2025-08-16 14:00", tz="UTC")   # sábado -> viernes 16:00
    assert fd_snapshot_time(sat) == pd.Timestamp("2025-08-15 16:00", tz="UTC")
    mon = pd.Timestamp("2025-08-18 19:00", tz="UTC")   # lunes -> viernes anterior
    assert fd_snapshot_time(mon) == pd.Timestamp("2025-08-15 16:00", tz="UTC")
    wed = pd.Timestamp("2025-08-20 19:00", tz="UTC")   # miércoles -> martes 12:00
    assert fd_snapshot_time(wed) == pd.Timestamp("2025-08-19 12:00", tz="UTC")
    fri = pd.Timestamp("2025-08-15 19:00", tz="UTC")   # viernes noche -> ese viernes 16:00
    assert fd_snapshot_time(fri) == pd.Timestamp("2025-08-15 16:00", tz="UTC")


def test_price_at_uses_last_price_before():
    hist = [{"t": 0, "p": 0.4}, {"t": 3600, "p": 0.5}, {"t": 7200, "p": 0.9}]
    assert _price_at(hist, 5400) == (0.5, 0.5)
    assert math.isnan(_price_at(hist, -1)[0])
