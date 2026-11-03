"""Avisos por ntfy: RAM, disco y colector parado. Sin dependencias salvo psutil.

Configuración por entorno:
  NTFY_TOPIC   tema de ntfy (si falta, los avisos solo van al log). Usa un nombre largo y aleatorio:
               en ntfy.sh público, quien conozca el tema puede leerlo.
  NTFY_SERVER  por defecto https://ntfy.sh
"""
from __future__ import annotations

import asyncio
import os
import shutil
import time
from pathlib import Path

import psutil
import requests

from futdata.common import log

COOLDOWN = 6 * 3600  # no repetir el mismo aviso antes de 6 h
CHECK_EVERY = 60
STALL_AFTER = 600  # s sin mensajes del websocket
RAM_WARN = 85  # % de memoria usada
DISK_WARN = (80, 90)  # % de disco: aviso y urgente


def notify(title: str, message: str, priority: str = "default", tags: str = "") -> None:
    topic = os.environ.get("NTFY_TOPIC")
    log.warning("ntfy [%s] %s: %s", priority, title, message)
    if not topic:
        return
    server = os.environ.get("NTFY_SERVER", "https://ntfy.sh").rstrip("/")
    try:
        requests.post(f"{server}/{topic}", data=message.encode(), timeout=10,
                      headers={"Title": title, "Priority": priority, "Tags": tags})
    except requests.RequestException as exc:
        log.error("ntfy falló: %s", exc)


def dir_size_gb(path: Path) -> float:
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file()) / 1e9


def problems(data_dir: Path, last_message: float | None, now: float) -> dict[str, tuple[str, str]]:
    """Alertas activas: clave -> (mensaje, prioridad). La clave sirve para el enfriamiento."""
    found = {}
    ram = psutil.virtual_memory().percent
    if ram >= RAM_WARN:
        found["ram"] = (f"RAM al {ram:.0f}%", "high")
    disk = shutil.disk_usage(data_dir)
    pct = disk.used / disk.total * 100
    if pct >= DISK_WARN[0]:
        urgent = pct >= DISK_WARN[1]
        found["disk"] = (f"Disco al {pct:.0f}% ({disk.free / 1e9:.1f} GB libres, datos {dir_size_gb(data_dir):.1f} GB). "
                         "Descarga y borra.", "urgent" if urgent else "high")
    if last_message is not None and now - last_message > STALL_AFTER:
        found["stall"] = (f"Sin mensajes del websocket desde hace {(now - last_message) / 60:.0f} min", "high")
    return found


async def watch(data_dir: Path, last_message) -> None:
    """Bucle de vigilancia. last_message es un callable que devuelve el instante del último mensaje."""
    sent: dict[str, float] = {}
    notify("Colector Polymarket iniciado", f"Datos en {data_dir}", tags="rocket")
    while True:
        await asyncio.sleep(CHECK_EVERY)
        now = time.time()
        active = problems(data_dir, last_message(), now)
        for key, (message, priority) in active.items():
            if now - sent.get(key, 0) >= COOLDOWN:
                sent[key] = now
                await asyncio.to_thread(notify, f"Polymarket: {key}", message, priority, "warning")
        for key in set(sent) - set(active):  # resuelta
            del sent[key]
            await asyncio.to_thread(notify, f"Polymarket: {key} resuelto", "Vuelve a la normalidad", "default", "white_check_mark")
