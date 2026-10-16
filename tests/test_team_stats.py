"""Tests del extractor de estadísticas por equipo (sin ficheros reales)."""
import json

from futdata import team_stats
from futdata.team_stats import _num, _snake


def test_num_parses_formats():
    assert _num("1.27") == 1.27
    assert _num("10 (50%)") == (10.0, 50.0)
    assert _num("") is None and _num(None) is None


def test_snake():
    assert _snake("possessionPct") == "possession_pct"
    assert _snake("ShotsOnTarget") == "shots_on_target"


def _write_summary(tmp_path, home_stats, away_stats):
    def team(side, stats):
        return {"homeAway": side, "statistics": [{"name": k, "displayValue": v} for k, v in stats.items()]}
    path = tmp_path / "espn" / "summary" / "SP1" / "2024" / "1.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"boxscore": {"teams": [team("home", home_stats), team("away", away_stats)]}}))


def test_espn_zero_team_is_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(team_stats, "RAW", tmp_path)
    _write_summary(tmp_path, {"possessionPct": "55", "totalShots": "12"},
                   {"possessionPct": "0", "totalShots": "0"})
    home, away = team_stats._espn_one(("m", "SP1", 2024, "1"))
    assert home["espn_total_shots"] == 12
    assert home["espn_possession_pct"] is None  # la posesión ya no suma 100
    assert away["espn_total_shots"] is None


def test_espn_normal_match_kept(tmp_path, monkeypatch):
    monkeypatch.setattr(team_stats, "RAW", tmp_path)
    _write_summary(tmp_path, {"possessionPct": "55", "totalShots": "12"},
                   {"possessionPct": "45", "totalShots": "8"})
    home, away = team_stats._espn_one(("m", "SP1", 2024, "1"))
    assert (home["espn_possession_pct"], away["espn_total_shots"]) == (55, 8)
