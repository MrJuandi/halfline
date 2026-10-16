"""Tests de data/processed/player_seasons.parquet. Se saltan sin el fichero."""
import pytest

from futdata.common import ROOT

PLAYER_SEASONS = ROOT / "data" / "processed" / "player_seasons.parquet"

pytestmark = pytest.mark.skipif(not PLAYER_SEASONS.exists(),
                                reason="sin data/processed/player_seasons.parquet")


@pytest.fixture(scope="module")
def ps():
    import pandas as pd
    return pd.read_parquet(PLAYER_SEASONS)


def test_key_columns_present(ps):
    required = {"player_id", "name", "league", "season", "team", "apps", "starts", "minutes",
                "goals", "assists", "xg", "shots", "rating_w", "avg_x", "avg_y", "role"}
    assert required <= set(ps.columns)


def test_minutes_non_negative(ps):
    assert (ps["minutes"].dropna() >= 0).all()


def test_goals_not_above_shots_plus_tolerance(ps):
    # Tolerancia de 5: penaltis y posibles inconsistencias de la fuente
    both = ps.dropna(subset=["goals", "shots"])
    assert (both["goals"] <= both["shots"] + 5).all()


def test_lamine_yamal_2025_in_sp1(ps):
    rows = ps[(ps["league"] == "SP1") & (ps["season"] == 2025)
              & ps["name"].fillna("").str.contains("Yamal")]
    assert not rows.empty
    assert rows["minutes"].max() > 0
