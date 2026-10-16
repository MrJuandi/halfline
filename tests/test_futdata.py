"""Tests de futdata sin red: se parchean Client, fetch_to y las rutas de salida con tmp_path."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from futdata import espn, understat
from futdata.common import current_season, fd_code


class FakeClient:
    def __init__(self, *args, **kwargs):
        pass


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def _espn_event(event_id, completed, date_str="2025-08-15T19:00Z"):
    return {
        "id": event_id,
        "date": date_str,
        "competitions": [{"status": {"type": {"completed": completed}}}],
    }


# ---------------------------------------------------------------- common

def test_fd_code():
    assert fd_code(2014) == "1415"
    assert fd_code(2025) == "2526"


def test_current_season():
    assert current_season(date(2026, 10, 13)) == 2026
    assert current_season(date(2026, 3, 1)) == 2025
    assert current_season(date(2026, 7, 1)) == 2026
    assert current_season(date(2026, 6, 30)) == 2025


# ---------------------------------------------------------------- ESPN

def test_espn_completed_events_from_scoreboard_dedupes_and_skips_pending():
    data = {"events": [
        _espn_event("1", True),
        _espn_event("2", False),
        _espn_event("1", True),          # duplicado
        _espn_event("3", True, "2025-08-16T12:30Z"),
    ]}
    assert espn.completed_events(data) == [("1", "2025-08-15"), ("3", "2025-08-16")]


def test_espn_completed_event_ids_reads_season_months_only(tmp_path, monkeypatch):
    monkeypatch.setattr(espn, "OUT", tmp_path)
    _write_json(espn.scoreboard_path("SP1", "202508"), {"events": [_espn_event("10", True)]})
    _write_json(espn.scoreboard_path("SP1", "202601"), {"events": [
        _espn_event("20", True, "2026-01-15T19:00Z"), _espn_event("21", False, "2026-01-16T19:00Z")]})
    # Mes de otra temporada (2026/27): no debe aparecer en la 2025
    _write_json(espn.scoreboard_path("SP1", "202607"), {"events": [_espn_event("99", True, "2026-08-20T19:00Z")]})
    assert espn.completed_event_ids("SP1", 2025) == ["10", "20"]
    assert espn.last_completed_date("SP1") == "2026-08-20"


def test_espn_should_fetch_month_rules():
    today = date(2026, 10, 13)
    missing = Path("/no/existe.json")
    # Hace más de 2 meses y existe -> saltar
    p_old = Path(__file__)  # cualquier fichero que existe
    assert espn.should_fetch_month("202608", p_old, False, today) is False
    # Hace más de 2 meses y no existe -> descargar
    assert espn.should_fetch_month("202608", missing, False, today) is True
    # Mes anterior y actual -> siempre
    assert espn.should_fetch_month("202609", p_old, False, today) is True
    assert espn.should_fetch_month("202610", p_old, False, today) is True
    # Hasta 2 meses en el futuro -> descargar; más allá -> no
    assert espn.should_fetch_month("202612", missing, False, today) is True
    assert espn.should_fetch_month("202701", missing, False, today) is False
    # force fuerza la descarga de los antiguos existentes
    assert espn.should_fetch_month("202608", p_old, True, today) is True


def test_espn_download_skips_existing_files(tmp_path, monkeypatch):
    monkeypatch.setattr(espn, "OUT", tmp_path)
    monkeypatch.setattr(espn, "Client", FakeClient)
    monkeypatch.setattr(espn, "_today", lambda: date(2026, 10, 13))

    # Calendario ya guardado de un mes antiguo; partidos 1 (ya con resumen) y 2 (sin resumen)
    _write_json(espn.scoreboard_path("SP1", "202507"), {"events": [
        _espn_event("1", True), _espn_event("2", True), _espn_event("3", False)]})
    _write_json(espn.summary_path("SP1", 2025, "1"), {"boxscore": {}})

    calls = []

    def fake_fetch_to(client, source, url, path, *, params=None, validate=None):
        calls.append((url, params))
        return True

    monkeypatch.setattr(espn, "fetch_to", fake_fetch_to)
    stats = espn.download(first=2025, last=2025, leagues=["SP1"])

    scoreboard_calls = [p["dates"] for u, p in calls if u.endswith("/scoreboard")]
    summary_calls = [p["event"] for u, p in calls if u.endswith("/summary")]
    assert "202507" not in scoreboard_calls                 # mes antiguo existente: saltado
    assert "202509" in scoreboard_calls                     # mes antiguo sin fichero: se descarga
    assert summary_calls == ["2"]                           # el 1 ya existía, el 3 no está completo
    assert stats["ok"] == len(calls)


# ---------------------------------------------------------------- Understat

def test_understat_result_match_ids_from_league_json():
    data = {
        "teams": {}, "players": {},
        "dates": [
            {"id": "111", "isResult": True, "datetime": "2025-08-15 19:00:00"},
            {"id": 222, "isResult": False, "datetime": "2025-08-16 19:00:00"},
            {"id": 333, "isResult": True, "datetime": "2025-08-17 17:00:00"},
            {"id": "111", "isResult": True, "datetime": "2025-08-15 19:00:00"},
        ],
    }
    assert understat.result_match_ids(data) == ["111", "333"]
    assert understat.last_result_date(data) == "2025-08-17"


def test_understat_download_skips_existing_league_and_fetches_result_matches(tmp_path, monkeypatch):
    monkeypatch.setattr(understat, "OUT", tmp_path)
    monkeypatch.setattr(understat, "Client", FakeClient)
    monkeypatch.setattr(understat, "_today", lambda: date(2026, 10, 13))
    _write_json(understat.league_path("SP1", 2014), {
        "teams": {}, "players": {},
        "dates": [{"id": "111", "isResult": True, "datetime": "2014-08-20 19:00:00"},
                  {"id": "222", "isResult": False, "datetime": "2014-08-21 19:00:00"}],
    })
    calls = []

    def fake_fetch_to(client, source, url, path, *, params=None, validate=None):
        calls.append(url)
        return True

    monkeypatch.setattr(understat, "fetch_to", fake_fetch_to)
    stats = understat.download(first=2014, last=2014, leagues=["SP1"])
    assert calls == [f"{understat.BASE}/getMatchData/111"]  # liga saltada, sólo partido jugado
    assert stats["aborted"] is False


def test_understat_aborts_after_five_consecutive_failures(tmp_path, monkeypatch):
    monkeypatch.setattr(understat, "OUT", tmp_path)
    monkeypatch.setattr(understat, "Client", FakeClient)
    calls = []

    def always_fail(client, source, url, path, *, params=None, validate=None):
        calls.append(url)
        return False

    monkeypatch.setattr(understat, "fetch_to", always_fail)
    stats = understat.download(first=2014, last=2026, leagues=["SP1"])
    assert len(calls) == understat.MAX_CONSECUTIVE_FAILURES == 5
    assert stats["aborted"] is True
    assert stats["error"] == 5


def test_understat_success_resets_failure_counter(tmp_path, monkeypatch):
    monkeypatch.setattr(understat, "OUT", tmp_path)
    monkeypatch.setattr(understat, "Client", FakeClient)
    calls = []

    def pattern(client, source, url, path, *, params=None, validate=None):
        calls.append(url)
        return len(calls) == 5  # 4 fallos, un éxito, luego fallos seguidos

    monkeypatch.setattr(understat, "fetch_to", pattern)
    stats = understat.download(first=2014, last=2026, leagues=["SP1"])
    # El éxito en la llamada 5 reinicia el contador: el aborto llega 5 fallos después (llamada 10)
    assert len(calls) == 10
    assert stats["aborted"] is True
