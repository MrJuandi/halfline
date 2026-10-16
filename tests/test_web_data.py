"""Tests de la capa web (futdata.web_data) y de la API Flask. Se saltan sin data/processed/matches.parquet."""
import json
from datetime import datetime, timezone

import pytest

from futdata.common import ROOT

MATCHES = ROOT / "data" / "processed" / "matches.parquet"


def _require_data():
    if not MATCHES.exists():
        pytest.skip("sin data/processed/matches.parquet")


def test_meta_has_five_leagues():
    _require_data()
    from futdata.web_data import meta
    data = meta()
    assert len(data["leagues"]) == 5
    assert {lg["code"] for lg in data["leagues"]} == {"SP1", "E0", "I1", "D1", "F1"}
    json.dumps(data, allow_nan=False)  # sin NaN


def test_table_2025_sp1():
    _require_data()
    from futdata.web_data import table
    data = table("SP1", 2025)
    rows = data["rows"]
    assert len(rows) == 20
    assert rows[0]["pts"] >= rows[-1]["pts"]
    assert sum(r["played"] for r in rows) == 2 * 380
    json.dumps(data, allow_nan=False)


def test_match_detail_sp1_2026_has_shots_momentum_and_possession():
    _require_data()
    from futdata.web_data import match_detail, matches
    found = None
    for item in matches(league="SP1", season=2026):
        detail = match_detail(item["match_id"])
        if detail["shots"] and detail["momentum"]:
            found = detail
            break
    assert found is not None, "ningún partido de SP1 2026 con tiros y momentum"
    assert all(0 <= s["x"] <= 105 for s in found["shots"] if s["x"] is not None)
    possession = next(s for s in found["stats"] if s["key"] == "possession")
    assert possession["home"] + possession["away"] == pytest.approx(100, abs=1.5)
    json.dumps(found, allow_nan=False)


def test_team_series_non_empty():
    _require_data()
    from futdata.web_data import table, team
    name = table("SP1", 2025)["rows"][0]["team"]
    data = team("SP1", name)
    assert data is not None
    assert len(data["series"]) > 0
    assert data["summary"]["played"] == len(data["matches"])


def test_upcoming_returns_future_kickoffs():
    _require_data()
    from futdata.web_data import upcoming
    now = datetime.now(timezone.utc)
    data = upcoming(21)
    assert isinstance(data, list)
    for item in data:
        assert datetime.fromisoformat(item["kickoff"]) > now


def test_api_meta_200_and_unknown_match_404():
    _require_data()
    from futdata.api import app
    client = app.test_client()
    response = client.get("/api/meta")
    assert response.status_code == 200
    assert response.get_json()["leagues"]
    missing = client.get("/api/matches/xxx")
    assert missing.status_code == 404
    assert missing.get_json()["error"] == "not_found"


def test_model_eval_matches_report():
    """La evaluación de la web recalcula el log-loss del test y coincide con model_report.json."""
    _require_data()
    from futdata.web_data import model_eval
    data = model_eval()
    if data is None:
        pytest.skip("sin informe del modelo")
    total = next(r for r in data["leagues"] if r["league"] is None)
    shown = next(r for r in data["ranking"] if r["model"] == data["model"])
    assert total["n"] == shown["n"]
    assert abs(total["model"]["logloss"] - shown["logloss"]) < 0.002
    for cal in (data["calibration"]["model"], data["calibration"]["market"]):
        assert all(0 <= c["freq"] <= 1 and c["n"] >= 30 for c in cal)
    json.dumps(data, allow_nan=False)


def test_match_detail_exposes_overround_and_model():
    """La ficha trae las cuotas medias tal cual, su margen y las probabilidades sin margen."""
    _require_data()
    from futdata.web_data import match_detail, matches
    m = next(x for x in matches(limit=200) if x["market"])
    d = match_detail(m["match_id"])
    o = d["pre_match"]["market"]["overround"]
    assert o is not None and 0 <= o < 0.15
    odds = d["pre_match"]["market"]["odds"]
    assert abs(sum(1 / v for v in odds.values()) - (1 + o)) < 0.002
    assert abs(sum(d["pre_match"]["market"]["pre"].values()) - 1) < 0.01
    model = d["pre_match"]["model"]
    if model is not None:
        assert abs(sum(model["probs"].values()) - 1) < 0.01


def test_markets_polymarket_has_no_margin():
    _require_data()
    from futdata.web_data import markets
    data = markets()
    if data is None:
        pytest.skip("sin datos de Polymarket")
    assert data["books"]["mean"] > 0.02 > abs(data["polymarket"]["mean"])
    assert sum(data["books"]["hist"]) == sum(data["polymarket"]["hist"]) == data["n"]


def test_upcoming_model_sums_to_one_and_uses_only_past_matches():
    """Las probabilidades de /api/upcoming suman 1 y solo usan partidos anteriores al saque inicial:
    con el historial cortado justo antes de un partido ya jugado se reproduce su predicción fuera
    de muestra de model_predictions.parquet, y un historial que lo incluye no predice."""
    _require_data()
    from futdata.matches import PROCESSED
    from futdata.models import data
    from futdata.web_data import SHOWN_MODEL, _model_by_id, elo_forecast, elo_state, upcoming
    report = PROCESSED / "model_report.json"
    if not report.is_file() or not _model_by_id():
        pytest.skip("sin informe del modelo")
    for item in upcoming(21):
        if item["model"] is not None:
            assert abs(sum(item["model"].values()) - 1) < 0.01

    params = json.loads(report.read_text())["elegidos"][SHOWN_MODEL]
    history = data.load()
    target = history[history.match_id.isin(_model_by_id().keys())].iloc[-1]
    past = history[history.kickoff < target.kickoff]
    probs = elo_forecast(elo_state(past, params), target.home, target.away, target.kickoff)
    assert probs is not None
    assert abs(sum(probs.values()) - 1) < 1e-9
    expected = _model_by_id()[target.match_id]
    assert all(abs(probs[k] - expected[k]) < 0.01 for k in probs)

    leaky = history[history.kickoff <= target.kickoff]
    assert elo_forecast(elo_state(leaky, params), target.home, target.away, target.kickoff) is None


def test_upcoming_market_from_fixtures_csv(tmp_path, monkeypatch):
    """Con filas de las cinco ligas en fixtures.csv (nombres y fecha local UK de Football-Data),
    upcoming() devuelve el mercado sin margen (método de potencia) de esos partidos."""
    _require_data()
    import numpy as np
    import pandas as pd

    from futdata import web_data
    from futdata.models.margin import fair
    picked = {}
    for item in web_data.upcoming(21):
        picked.setdefault(item["league"], item)
    if len(picked) < 5:
        pytest.skip("sin partidos programados de las cinco ligas en ESPN")
    odds = (2.10, 3.40, 3.60)  # margen ~6 %
    rows = [{"Div": it["league"],
             "Date": pd.Timestamp(it["kickoff"]).tz_convert("Europe/London").strftime("%d/%m/%Y"),
             "Time": "15:00", "HomeTeam": it["home"], "AwayTeam": it["away"],
             "AvgH": odds[0], "AvgD": odds[1], "AvgA": odds[2]} for it in picked.values()]
    path = tmp_path / "fixtures.csv"
    pd.DataFrame(rows).to_csv(path, index=False, encoding="utf-8-sig")
    monkeypatch.setattr(web_data, "FIXTURES", path)

    expected = fair(np.array([odds], dtype=float))[0]
    by_id = {it["espn_id"]: it for it in web_data.upcoming(21)}
    for it in picked.values():
        market = by_id[it["espn_id"]]["market"]
        assert market is not None, (it["league"], it["home"], it["away"])
        assert abs(sum(market.values()) - 1) < 0.01  # _clean redondea a 3 decimales
        assert np.allclose([market["home"], market["draw"], market["away"]], expected, atol=1e-3)
