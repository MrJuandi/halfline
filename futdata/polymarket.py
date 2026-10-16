"""Polymarket: mercados 1X2 por partido (tres preguntas sí/no: gana local, empate, gana visitante)
y evolución horaria de su precio. APIs públicas sin clave.

Cobertura comprobada (14/10/2026): las 5 ligas desde agosto de 2025 (2025/26 en adelante).
  - Gamma API (/events?series_id=…): partidos, mercados, volumen, comisiones, marcador final.
  - CLOB (/prices-history): precio de la acción "Sí" cada hora (fidelity=60). Con interval=max
    devuelve vacío en mercados cerrados: hay que pasar startTs y endTs.
El precio histórico es el de la API (punto medio / última operación), no la horquilla real.

Destino:
  data/raw/polymarket/events/<LIGA>/<offset>.json            (páginas de 100 partidos cerrados)
  data/raw/polymarket/prices/<LIGA>/<slug del mercado>.json   (historial de precio del "Sí")
"""
from __future__ import annotations

import json
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

from futdata.common import RAW, Client, fetch_to, log, validate_json

SOURCE = "polymarket"
GAMMA = "https://gamma-api.polymarket.com"
CLOB = "https://clob.polymarket.com"
OUT = RAW / SOURCE
SERIES = {"E0": 10188, "SP1": 10193, "D1": 10194, "F1": 10195, "I1": 10203}
PAGE = 100
WORKERS = 8
MATCH_SLUG = re.compile(r"^[a-z0-9]+-[a-z0-9]+-[a-z0-9]+-\d{4}-\d{2}-\d{2}$")


def _ts(text: str) -> int:
    return int(datetime.fromisoformat(text.replace("Z", "+00:00").replace(" ", "T")).timestamp())


def download_events(client: Client, league: str) -> list[dict]:
    """Descarga todas las páginas de partidos cerrados de la liga (siempre, para captar los nuevos)."""
    events, offset = [], 0
    while True:
        path = OUT / "events" / league / f"{offset:05d}.json"
        params = {"series_id": SERIES[league], "closed": "true", "limit": PAGE, "offset": offset,
                  "order": "startDate", "ascending": "true"}
        if not fetch_to(client, SOURCE, f"{GAMMA}/events", path, params=params, validate=validate_json):
            break
        page = json.loads(path.read_text())
        events += page
        if len(page) < PAGE:
            break
        offset += PAGE
    return events


def is_match_1x2(event: dict) -> bool:
    """El evento principal del partido: '<liga>-<local>-<visitante>-AAAA-MM-DD' con sus 3 mercados.
    La serie incluye además eventos de marcador exacto, goles, hándicap y jugadores."""
    return bool(MATCH_SLUG.match(event.get("slug", ""))) and len(event.get("markets", [])) == 3


def _price_job(client: Client, league: str, event: dict, market: dict) -> bool:
    path = OUT / "prices" / league / f"{market['slug']}.json"
    if path.exists():
        return True
    token = json.loads(market["clobTokenIds"])[0]  # acción "Sí"
    start = _ts(market.get("startDate") or event["createdAt"])
    # aplazados: endDate puede ser anterior a la creación del mercado; se toma la fecha más tardía
    end = max(_ts(x) for x in (event.get("endDate"), event.get("startTime"), market.get("closedTime"),
                               market.get("startDate")) if x) + int(timedelta(hours=4).total_seconds())
    params = {"market": token, "startTs": start, "endTs": end, "fidelity": 60}
    return fetch_to(client, SOURCE, f"{CLOB}/prices-history", path, params=params, validate=validate_json)


def download(leagues: list[str] | None = None) -> dict:
    gamma = Client(min_interval=0.2)
    clobs = threading.local()  # un cliente por hilo

    def job(args):
        if not hasattr(clobs, "c"):
            clobs.c = Client(min_interval=0.1)
        return _price_job(clobs.c, *args)

    summary = {}
    for league in leagues or list(SERIES):
        events = download_events(gamma, league)
        jobs = [(league, e, m) for e in events if is_match_1x2(e)
                for m in e.get("markets", []) if m.get("clobTokenIds")]
        with ThreadPoolExecutor(WORKERS) as pool:
            ok = sum(pool.map(job, jobs))
        summary[league] = {"partidos": len(events), "mercados": len(jobs), "precios_ok": ok}
        log.info("polymarket %s: %s", league, summary[league])
    return summary



# ---------------------------------------------------------------- tabla procesada

def fd_snapshot_time(kickoff):
    """Hora aproximada (UTC) en que Football-Data captura las cuotas pre-cierre: martes 12:00
    para partidos de martes a jueves; viernes 16:00 para el resto (fin de semana y lunes)."""
    import pandas as pd
    k = kickoff.tz_convert("UTC")
    day = k.normalize()
    if k.weekday() in (1, 2, 3):
        snap = day - pd.Timedelta(days=k.weekday() - 1) + pd.Timedelta(hours=12)
    else:
        snap = day - pd.Timedelta(days=(k.weekday() - 4) % 7) + pd.Timedelta(hours=16)
    return snap if snap < k else snap - pd.Timedelta(days=7)


def _price_at(history: list[dict], ts: float) -> tuple[float, float]:
    """Último precio con t <= ts y su antigüedad en horas (NaN si no hay)."""
    best = None
    for point in history:
        if point["t"] <= ts:
            best = point
        else:
            break
    if best is None:
        return float("nan"), float("nan")
    return float(best["p"]), (ts - best["t"]) / 3600


def build():
    """data/processed/polymarket.parquet: un partido por fila con precios del 1X2 en dos momentos.

    - pm_pre_*: a la hora de la captura pre-cierre de Football-Data (comparable con mkt_p_*).
    - pm_close_*: último precio horario antes del inicio (comparable con close_p_*).
    Precios crudos de la acción "Sí" (suman ~1); *_age_h = antigüedad del último precio.
    """
    import pandas as pd
    from futdata.matches import PROCESSED

    rows = []
    for league in SERIES:
        for page in sorted((OUT / "events" / league).glob("*.json")):
            for e in json.loads(page.read_text()):
                if not is_match_1x2(e):
                    continue
                teams = {t.get("ordering"): t for t in e.get("teams") or []}
                markets = {m["slug"]: m for m in e.get("markets", [])}
                if set(teams) != {"home", "away"} or not e.get("score"):
                    continue
                slugs = {"home": f"{e['slug']}-{teams['home']['abbreviation']}", "draw": f"{e['slug']}-draw",
                         "away": f"{e['slug']}-{teams['away']['abbreviation']}"}
                if not all(s in markets for s in slugs.values()):
                    continue
                kickoff = pd.Timestamp(e["startTime"])
                hg, ag = (int(x) for x in e["score"].split("-")[:2])
                row = {"pm_slug": e["slug"], "league": league, "kickoff_pm": kickoff,
                       "pm_home": teams["home"].get("alias") or teams["home"]["name"],
                       "pm_away": teams["away"].get("alias") or teams["away"]["name"],
                       "pm_home_goals": hg, "pm_away_goals": ag, "pm_volume": float(e.get("volume") or 0),
                       "pm_fees": any(m.get("feesEnabled") for m in markets.values())}
                snaps = {"pre": fd_snapshot_time(kickoff).timestamp(),
                         "close": (kickoff - pd.Timedelta(minutes=1)).timestamp()}
                for label, slug in slugs.items():
                    path = OUT / "prices" / league / f"{slug}.json"
                    hist = json.loads(path.read_text()).get("history", []) if path.exists() else []
                    row[f"pm_volume_{label}"] = float(markets[slug].get("volume") or 0)
                    for snap, ts in snaps.items():
                        row[f"pm_{snap}_{label}"], row[f"pm_{snap}_age_h_{label}"] = _price_at(hist, ts)
                rows.append(row)
    pm = pd.DataFrame(rows)

    # Emparejar con matches.parquet: nombres por votos (misma liga, marcador y fecha ±1 día)
    matches = pd.read_parquet(PROCESSED / "matches.parquet")
    pm["date"] = pm.kickoff_pm.dt.tz_convert("UTC").dt.tz_localize(None).dt.normalize()
    cand = pm.merge(matches[["match_id", "league", "date", "home", "away", "home_goals", "away_goals"]],
                    left_on=["league", "pm_home_goals", "pm_away_goals"],
                    right_on=["league", "home_goals", "away_goals"], suffixes=("", "_m"))
    cand = cand[(cand.date - cand.date_m).abs() <= pd.Timedelta(days=1)]
    votes = pd.concat([cand[["league", "pm_home", "home"]].set_axis(["league", "pm", "team"], axis=1),
                       cand[["league", "pm_away", "away"]].set_axis(["league", "pm", "team"], axis=1)])
    names = votes.value_counts().reset_index().drop_duplicates(["league", "pm"]).set_index(["league", "pm"]).team
    pm["home"] = names.reindex(list(zip(pm.league, pm.pm_home))).values
    pm["away"] = names.reindex(list(zip(pm.league, pm.pm_away))).values
    linked = pm.merge(matches[["match_id", "league", "date", "home", "away"]], on=["league", "home", "away"],
                      suffixes=("", "_m"))
    linked = linked[(linked.date - linked.date_m).abs() <= pd.Timedelta(days=1)].drop(columns=["date_m"])
    linked = linked.drop_duplicates("match_id")
    log.info("polymarket: %d partidos, %d emparejados", len(pm), len(linked))
    linked.to_parquet(PROCESSED / "polymarket.parquet", index=False)
    return linked


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    print(download())
    print(len(build()), "partidos emparejados")
