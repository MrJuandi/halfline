"""Escudos de los equipos y color dominante de marca.

Descarga el escudo (.webp) de cada equipo de web_data._team_identity() a data/raw/crests/<slug>.webp
(saltando los ya descargados) y calcula su color dominante.

Salida: data/processed/team_colors.json  {canónico: {"file": "<slug>.webp", "color": "#rrggbb"}}

Uso:  python -m futdata.crests
"""
from __future__ import annotations

import io
import json
import re
from pathlib import Path

import numpy as np
from PIL import Image

from futdata.common import RAW, Client, fetch_to, write_raw
from futdata.matches import PROCESSED

CREST_DIR = RAW / "crests"
COLORS_FILE = PROCESSED / "team_colors.json"

# Escudos cuyo color más frecuente no es el que identifica al club (dorados, blanco y negro…)
COLOR_OVERRIDES = {
    "Barcelona": "#a50044", "Real Madrid": "#febe10", "Juventus": "#d4d4d4", "Spezia": "#a3a3a3",
    "Newcastle": "#d4d4d4", "Fulham": "#d4d4d4", "Valencia": "#ee3524", "Ath Madrid": "#cb3524",
}
BUCKET = 24          # cuantización de canales para agrupar colores parecidos
SAT_MIN = 0.25       # saturación HSV mínima para considerar un color "de marca"


def slug(name: str) -> str:
    """'Bayern Munich' -> 'bayern-munich'."""
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def _check_image(content: bytes) -> None:
    try:
        with Image.open(io.BytesIO(content)) as img:
            img.verify()
    except Exception as exc:  # PIL lanza tipos varios; fetch_to espera ValueError
        raise ValueError(f"imagen no válida: {exc}") from exc


def _most_frequent(rgb: np.ndarray) -> np.ndarray:
    """Color medio de los píxeles del grupo cuantizado más frecuente."""
    q = rgb // BUCKET
    code = q[:, 0] * 10000 + q[:, 1] * 100 + q[:, 2]
    values, counts = np.unique(code, return_counts=True)
    top = values[np.argmax(counts)]
    return np.median(rgb[code == top], axis=0)


def dominant_color(path: Path | str) -> str | None:
    """Color dominante '#rrggbb' de una imagen, o None si no tiene píxeles opacos.

    Ignora píxeles transparentes (alpha < 128), casi blancos (todos los canales > 230) y casi
    negros (todos < 35). Del resto descarta los grises (saturación HSV < 0.25). Si no queda
    ninguno, vuelve a usar los píxeles sin el filtro de gris; si tampoco hay, usa todos los opacos.
    """
    with Image.open(path) as img:
        img = img.convert("RGBA")
        img.thumbnail((128, 128))
        px = np.asarray(img, dtype=np.int32).reshape(-1, 4)
    px = px[px[:, 3] >= 128]
    if px.size == 0:
        return None
    rgb = px[:, :3]
    mx = rgb.max(axis=1)
    mn = rgb.min(axis=1)
    sat = (mx - mn) / np.maximum(mx, 1)
    not_white = ~(rgb > 230).all(axis=1)
    not_black = ~(rgb < 35).all(axis=1)
    base = not_white & not_black
    keep = base & (sat >= SAT_MIN)
    if keep.any():
        chosen = rgb[keep]
    elif base.any():
        chosen = rgb[base]
    else:
        chosen = rgb
    r, g, b = (int(round(c)) for c in _most_frequent(chosen))
    return f"#{r:02x}{g:02x}{b:02x}"


def main() -> None:
    from futdata.web_data import _team_identity  # import tardío: evita ciclos al cargar el módulo

    client = Client(min_interval=0.2)
    CREST_DIR.mkdir(parents=True, exist_ok=True)
    colors: dict = {}
    identity = _team_identity()
    for canonical in sorted(identity):
        # crest_remote es la URL original; crest puede ya apuntar a la API local
        url = identity[canonical].get("crest_remote") or identity[canonical].get("crest")
        if not url:
            print(f"sin escudo: {canonical}")
            continue
        path = CREST_DIR / f"{slug(canonical)}.webp"
        if not path.is_file():
            if not fetch_to(client, "crest", url, path, validate=_check_image):
                print(f"fallo descargando: {canonical}")
                continue
        colors[canonical] = {"file": path.name, "color": dominant_color(path)}

    for team, color in COLOR_OVERRIDES.items():
        if team in colors:
            colors[team]["color"] = color
    write_raw(COLORS_FILE, json.dumps(colors, ensure_ascii=False, indent=2).encode("utf-8"))
    print(f"Escrito {COLORS_FILE} ({len(colors)} equipos)")
    for name, info in colors.items():
        print(f"  {name}: {info['color']}")


if __name__ == "__main__":
    main()
