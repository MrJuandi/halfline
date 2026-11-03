import gzip
import json
from datetime import datetime, timedelta, timezone

from futdata import monitor, polymarket_live as live


def _event(slug, start, closed=False):
    market = {"slug": f"{slug}-home", "question": "¿Gana el local?", "closed": closed, "conditionId": "0xabc",
              "outcomes": json.dumps(["Yes", "No"]), "clobTokenIds": json.dumps([f"{slug}-yes", f"{slug}-no"])}
    return {"slug": slug, "startTime": start.isoformat().replace("+00:00", "Z"), "markets": [market]}


class FakeSession:
    def __init__(self, events):
        self.events, self.headers = events, {}

    def get(self, url, params, timeout):
        page = self.events if params["offset"] == 0 else []
        return type("R", (), {"json": lambda self: page})()


def test_discover_filtra_por_ventana_y_mercados_cerrados(monkeypatch):
    now = datetime(2026, 11, 3, 12, tzinfo=timezone.utc)
    events = [_event("pronto", now + timedelta(days=2)), _event("lejos", now + timedelta(days=30)),
              _event("viejo", now - timedelta(days=3)), _event("cerrado", now + timedelta(days=1), closed=True)]
    monkeypatch.setattr(live.requests, "Session", lambda: FakeSession(events))
    monkeypatch.setattr(live, "SERIES", {"E0": 1})
    found = live.discover(now)
    assert set(found) == {"pronto-yes", "pronto-no"}
    assert found["pronto-yes"]["outcome"] == "Yes" and found["pronto-yes"]["league"] == "E0"


def test_recorder_escribe_y_comprime_horas_cerradas(tmp_path, monkeypatch):
    monkeypatch.setattr(live, "OUT", tmp_path)
    rec = live.Recorder()
    rec.write('{"event_type":"book"}')
    rec.flush()
    old = tmp_path / "ws" / "2020-01-01" / "00.jsonl"
    old.parent.mkdir(parents=True)
    old.write_text("1\t{}\n")
    assert rec.compress_closed() == 1
    assert not old.exists() and gzip.open(f"{old}.gz", "rt").read() == "1\t{}\n"
    current = next(tmp_path.glob("ws/*/*.jsonl"))
    ts, raw = current.read_text().rstrip("\n").split("\t", 1)
    assert ts.isdigit() and json.loads(raw) == {"event_type": "book"}


def test_problems_detecta_parada(tmp_path):
    assert "stall" in monitor.problems(tmp_path, last_message=0, now=monitor.STALL_AFTER + 1)
    assert "stall" not in monitor.problems(tmp_path, last_message=None, now=1e9)
