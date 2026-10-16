"""Tests de fuga temporal en las variables pre-partido (datos sintéticos)."""
import numpy as np
import pandas as pd

from futdata.features import elo_ratings, form_features


def _rows():
    """Dos equipos que se enfrentan 6 veces; una fila por equipo y partido."""
    out = []
    for i in range(6):
        kickoff = pd.Timestamp("2024-08-01", tz="UTC") + pd.Timedelta(days=7 * i)
        mid = f"m{i}"
        for side, team, opp, xg in (("home", "A", "B", 1.0 + i), ("away", "B", "A", 0.5)):
            out.append({"match_id": mid, "side": side, "team": team, "opponent": opp, "kickoff": kickoff,
                        "xg_for": xg, "xg_against": 0.5 if team == "A" else 1.0 + i,
                        "possession": 50.0, "points": 3 if team == "A" else 0})
    return pd.DataFrame(out)


def test_first_match_has_no_form_and_window_uses_previous_only():
    f = form_features(_rows()).set_index(["match_id", "team"])
    assert np.isnan(f.loc[("m0", "A"), "r5_xg_for"])          # sin partidos previos
    assert f.loc[("m3", "A"), "r5_xg_for"] == np.mean([1, 2, 3])  # m0..m2, no m3
    assert f.loc[("m3", "A"), "rest_days"] == 7
    assert f.loc[("m3", "A"), "n_prev"] == 3


def test_changing_a_match_does_not_change_its_own_features():
    rows = _rows()
    changed = rows.copy()
    changed.loc[changed.match_id == "m4", ["xg_for", "points"]] = 99
    a = form_features(rows).set_index(["match_id", "team"]).drop(columns="kickoff")
    b = form_features(changed).set_index(["match_id", "team"]).drop(columns="kickoff")
    pd.testing.assert_frame_equal(a.loc["m4"], b.loc["m4"])
    assert not a.loc["m5"].equals(b.loc["m5"])                 # el siguiente sí lo ve


def test_elo_uses_only_previous_results():
    matches = pd.DataFrame({
        "match_id": ["m0", "m1"], "home": ["A", "A"], "away": ["B", "B"],
        "home_goals": [3, 0], "away_goals": [0, 0],
        "kickoff": pd.to_datetime(["2024-08-01", "2024-08-08"], utc=True)})
    elo = elo_ratings(matches).set_index("match_id")
    assert elo.loc["m0", "home_elo"] == elo.loc["m0", "away_elo"] == 1500
    assert elo.loc["m1", "home_elo"] > 1500 > elo.loc["m1", "away_elo"]
