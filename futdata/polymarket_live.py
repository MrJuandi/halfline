"""Polymarket en vivo: graba el order book de todos los mercados de partidos de las 5 ligas.

La API no guarda el libro histórico, así que hay que capturarlo mientras ocurre.
  - Gamma API: descubre los eventos abiertos de cada liga (1X2, goles, hándicap, marcador exacto, jugadores…).
  - WebSocket del CLOB (canal market): snapshot del libro al suscribirse y después cada cambio
    (book, price_change, last_trade_price, tick_size_change).

Destino (cada línea del ws es "<ms de recepción>\\t<mensaje tal cual>"):
  data/raw/polymarket_live/ws/AAAA-MM-DD/HH.jsonl[.gz]   mensajes del websocket (UTC, .gz al cerrar la hora)
  data/raw/polymarket_live/meta/AAAA-MM-DD.jsonl         catálogo: token -> liga, evento, mercado, resultado

Uso: python -m futdata.polymarket_live            (Ctrl+C para parar)
Avisos de RAM, disco y parada por ntfy: ver futdata/monitor.py.
"""
from __future__ import annotations

import asyncio
import gzip
import json
import os
import shutil
import time
from datetime import datetime, timedelta, timezone

import requests
import websockets

from futdata import monitor
from futdata.common import RAW, USER_AGENT, log
from futdata.polymarket import GAMMA, SERIES

WS_URL = "wss://ws-subscriptions-clob.polymarket.com/ws/market"
OUT = RAW / "polymarket_live"
SHARD = 500  # tokens por conexión
REDISCOVER_EVERY = 1800  # s
PING_EVERY = 10  # s
LOG_EVERY = 60  # s
HORIZON = timedelta(days=10)  # cuánto antes del partido empezamos a grabar
GRACE = timedelta(hours=5)  # cuánto después del inicio seguimos (partido + prórroga)


def _parse(text: str) -> datetime | None:
    return datetime.fromisoformat(text.replace("Z", "+00:00").replace(" ", "T")) if text else None


def discover(now: datetime | None = None) -> dict[str, dict]:
    """token -> metadatos de todos los mercados de partidos en la ventana [ahora-GRACE, ahora+HORIZON]."""
    now = now or datetime.now(timezone.utc)
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    tokens = {}
    for league, series_id in SERIES.items():
        offset = 0
        while True:
            params = {"series_id": series_id, "closed": "false", "limit": 100, "offset": offset,
                      "order": "startDate", "ascending": "true"}
            page = session.get(f"{GAMMA}/events", params=params, timeout=30).json()
            for event in page:
                start = _parse(event.get("startTime") or event.get("endDate"))
                if start is None or not now - GRACE <= start <= now + HORIZON:
                    continue
                for market in event.get("markets", []):
                    if not market.get("clobTokenIds") or market.get("closed"):
                        continue
                    outcomes = json.loads(market.get("outcomes") or "[]")
                    for i, token in enumerate(json.loads(market["clobTokenIds"])):
                        tokens[token] = {"token": token, "league": league, "event": event["slug"],
                                         "market": market["slug"], "question": market.get("question"),
                                         "outcome": outcomes[i] if i < len(outcomes) else None,
                                         "start": event.get("startTime"), "condition": market.get("conditionId")}
            if len(page) < 100:
                break
            offset += 100
    return tokens


class Recorder:
    """Escribe los mensajes en ficheros por hora y comprime las horas ya cerradas."""

    def __init__(self):
        self.file, self.key = None, None
        self.last_message: float | None = None
        self.count = 0

    def write(self, raw: str) -> None:
        now = datetime.now(timezone.utc)
        key = (now.strftime("%Y-%m-%d"), now.strftime("%H"))
        if key != self.key:
            if self.file:
                self.file.close()
            folder = OUT / "ws" / key[0]
            folder.mkdir(parents=True, exist_ok=True)
            self.file, self.key = open(folder / f"{key[1]}.jsonl", "a", buffering=1 << 16), key
        self.file.write(f"{int(now.timestamp() * 1000)}\t{raw}\n")
        self.count += 1

    def flush(self) -> None:
        if self.file:
            self.file.flush()

    def compress_closed(self) -> int:
        current = None if self.key is None else OUT / "ws" / self.key[0] / f"{self.key[1]}.jsonl"
        done = 0
        for path in sorted((OUT / "ws").glob("*/*.jsonl")):
            if path == current:
                continue
            with open(path, "rb") as src, gzip.open(f"{path}.gz.tmp", "wb", compresslevel=6) as dst:
                shutil.copyfileobj(src, dst)
            os.replace(f"{path}.gz.tmp", f"{path}.gz")
            path.unlink()
            done += 1
        return done


def save_meta(new: list[dict]) -> None:
    folder = OUT / "meta"
    folder.mkdir(parents=True, exist_ok=True)
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    with open(folder / f"{day}.jsonl", "a") as f:
        for row in new:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


async def shard(name: str, tokens: list[str], active: set[str], rec: Recorder) -> None:
    """Una conexión websocket con reconexión; al reconectar solo pide los tokens aún vigentes."""
    backoff = 1
    while True:
        wanted = [t for t in tokens if t in active]
        if not wanted:
            log.info("%s: sin tokens vigentes, termina", name)
            return
        try:
            async with websockets.connect(WS_URL, ping_interval=None, max_size=None, open_timeout=20) as ws:
                await ws.send(json.dumps({"assets_ids": wanted, "type": "market"}))
                log.info("%s: suscrito a %d tokens", name, len(wanted))
                backoff = 1
                while True:
                    try:
                        raw = await asyncio.wait_for(ws.recv(), PING_EVERY)
                    except asyncio.TimeoutError:
                        await ws.send("PING")
                        continue
                    rec.last_message = time.time()
                    if raw != "PONG":
                        rec.write(raw)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - cualquier fallo de red: reconectar
            log.warning("%s: %s; reconecto en %ds", name, exc, backoff)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 60)


async def housekeeping(rec: Recorder) -> None:
    last_count, last_compress, last_log = 0, 0.0, time.time()
    while True:
        await asyncio.sleep(5)
        rec.flush()
        now = time.time()
        if now - last_compress >= 600:
            last_compress = now
            await asyncio.to_thread(rec.compress_closed)
        if now - last_log >= LOG_EVERY:
            log.info("%.1f mensajes/s", (rec.count - last_count) / (now - last_log))
            last_count, last_log = rec.count, now


async def run() -> None:
    rec, active, known, shards = Recorder(), set(), set(), []
    OUT.mkdir(parents=True, exist_ok=True)
    background = [asyncio.create_task(housekeeping(rec)),
                  asyncio.create_task(monitor.watch(OUT, lambda: rec.last_message))]
    try:
        while True:
            try:
                found = await asyncio.to_thread(discover)
            except Exception as exc:  # noqa: BLE001 - Gamma caído: seguimos con lo que hay
                log.warning("descubrimiento falló: %s", exc)
                found = None
            if found is not None:
                active.clear()
                active.update(found)
                new = [meta for token, meta in found.items() if token not in known]
                if new:
                    save_meta(new)
                    known.update(m["token"] for m in new)
                    for i in range(0, len(new), SHARD):
                        chunk = [m["token"] for m in new[i:i + SHARD]]
                        shards.append(asyncio.create_task(shard(f"ws{len(shards)}", chunk, active, rec)))
                log.info("descubiertos %d tokens (%d nuevos), %d conexiones", len(found), len(new), len(shards))
            await asyncio.sleep(REDISCOVER_EVERY)
    finally:
        for task in background + shards:
            task.cancel()
        rec.flush()


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        pass
