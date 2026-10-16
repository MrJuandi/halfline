"""Polymarket por momentos: ¿cuándo deja de equivocarse más que nuestro modelo?

Cada partido abre en Polymarket ~13 días antes (mediana 322 h). Con el precio horario del "Sí"
de los tres mercados (local, empate, visitante) se mide, en varios momentos:
  - después de abrir: 0 h (apertura), 1 h, 6 h, 24 h y 72 h;
  - antes del partido: 10 d, 7 d, 5 d, 3 d, 1 d, 6 h y 1 h.
Nunca se usa un precio de la última hora antes del inicio ni posterior.

Mercado formado: los tres "Sí" suman entre FORMED_LO y FORMED_HI. Al abrir, cada "Sí" vale ≈ 0,50
(punto medio de un libro vacío) y la suma ronda 1,3: no son precios a los que se pueda operar.
Solo se comparan mercados formados (normalizados a suma 1) con el modelo, en los mismos partidos.

Estrategias (por 1 $): comprar el "Sí" del resultado con mayor modelo − precio si supera el umbral,
pagando precio + COST. (a) mantener hasta el final: 1 / (precio + coste) − 1 si acierta, −1 si no;
(b) vender 1 h antes del partido: (precio_1h − coste) / (precio + coste) − 1.

Modelo: MODEL de model_predictions.parquet (fuera de muestra). Usa solo partidos ya jugados, así que
a 13 días vista sabe lo mismo que el día del partido salvo si el equipo juega entre medias.

Requiere: python -m futdata.polymarket y python -m futdata.models.evaluate.
Salida:   data/processed/polymarket_horizons.json
Uso:      python -m futdata.models.pm_horizons
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from futdata.matches import PROCESSED
from futdata.models import data
from futdata.models.evaluate import boot_ci, logloss_rows
from futdata.polymarket import OUT, SERIES, _price_at, is_match_1x2

LABELS = ["home", "draw", "away"]
MODEL = "Elo + plantilla"
AFTER_OPEN = {"apertura": 0, "ap+1h": 1, "ap+6h": 6, "ap+24h": 24, "ap+72h": 72}
BEFORE_KICKOFF = {"10d": 240, "7d": 168, "5d": 120, "3d": 72, "1d": 24, "6h": 6, "1h": 1}
FORMED_LO, FORMED_HI = 0.97, 1.06
COST = 0.01
EDGES = [0.03, 0.05, 0.08]
TRADE_AT = ["ap+6h", "ap+24h", "ap+72h", "10d", "7d", "5d", "3d"]


def moment_ts(name: str, opened: float, kickoff: float) -> float:
    """Instante (Unix) de un momento, o NaN si cae en la última hora antes del inicio o después."""
    ts = opened + AFTER_OPEN[name] * 3600 if name in AFTER_OPEN else kickoff - BEFORE_KICKOFF[name] * 3600
    return ts if opened <= ts <= kickoff - 3600 else float("nan")


def formed(raw: np.ndarray) -> np.ndarray:
    s = raw.sum(1)
    return (s >= FORMED_LO) & (s <= FORMED_HI)


def _market_slugs() -> dict:
    """slug del partido -> (liga, {local/empate/visitante: slug del mercado})."""
    out = {}
    for league in SERIES:
        for page in sorted((OUT / "events" / league).glob("*.json")):
            for e in json.loads(page.read_text()):
                teams = {t.get("ordering"): t for t in e.get("teams") or []}
                if is_match_1x2(e) and set(teams) == {"home", "away"}:
                    out[e["slug"]] = (league, {"home": f"{e['slug']}-{teams['home']['abbreviation']}",
                                               "draw": f"{e['slug']}-draw",
                                               "away": f"{e['slug']}-{teams['away']['abbreviation']}"})
    return out


def price_table() -> pd.DataFrame:
    """Un partido por fila: horas entre apertura e inicio y precio crudo del "Sí" en cada momento."""
    pm = pd.read_parquet(PROCESSED / "polymarket.parquet").dropna(subset=["match_id"])
    slugs = _market_slugs()
    rows = []
    for r in pm.itertuples():
        league, markets = slugs[r.pm_slug]
        paths = {k: OUT / "prices" / league / f"{s}.json" for k, s in markets.items()}
        if not all(p.exists() for p in paths.values()):
            continue
        hist = {k: json.loads(p.read_text()).get("history", []) for k, p in paths.items()}
        if any(not h for h in hist.values()):
            continue
        kickoff = r.kickoff_pm.timestamp()
        opened = max(h[0]["t"] for h in hist.values())
        row = {"match_id": r.match_id, "open_h": (kickoff - opened) / 3600}
        for name in [*AFTER_OPEN, *BEFORE_KICKOFF]:
            ts = moment_ts(name, opened, kickoff)
            for k, h in hist.items():
                row[f"{name}_{k}"] = _price_at(h, ts)[0] if np.isfinite(ts) else np.nan
        rows.append(row)
    return pd.DataFrame(rows)


def load() -> pd.DataFrame:
    df = data.load()[["match_id", "result"]]
    preds = pd.read_parquet(PROCESSED / "model_predictions.parquet")
    cols = [f"{MODEL}|p_{l}" for l in LABELS]
    return (price_table().merge(df, on="match_id").merge(preds[["match_id", *cols]], on="match_id")
            .dropna(subset=cols).reset_index(drop=True))


def raw_prices(df: pd.DataFrame, name: str) -> np.ndarray:
    return df[[f"{name}_{l}" for l in LABELS]].to_numpy(float)


def accuracy(df: pd.DataFrame) -> list:
    y = df.result.to_numpy()
    model = df[[f"{MODEL}|p_{l}" for l in LABELS]].to_numpy()
    rows = []
    for name in [*AFTER_OPEN, *BEFORE_KICKOFF]:
        raw = raw_prices(df, name)
        f = formed(raw) & np.isfinite(raw).all(1)
        p = raw[f] / raw[f].sum(1, keepdims=True)
        pm_ll, mod_ll = logloss_rows(p, y[f]), logloss_rows(model[f], y[f])
        rows.append({"momento": name, "formados": float(f.mean()), "n": int(f.sum()),
                     "suma_mediana": float(np.nanmedian(raw.sum(1))),
                     "polymarket": float(pm_ll.mean()) if f.any() else None,
                     "modelo": float(mod_ll.mean()) if f.any() else None,
                     "pm_menos_modelo": float((pm_ll - mod_ll).mean()) if f.any() else None,
                     "ic": boot_ci(pm_ll - mod_ll) if f.sum() > 1 else None})
    return rows


def strategies(df: pd.DataFrame) -> list:
    y = df.result.to_numpy()
    model = df[[f"{MODEL}|p_{l}" for l in LABELS]].to_numpy()
    last = raw_prices(df, "1h")
    rows = []
    for name in TRADE_AT:
        raw = raw_prices(df, name)
        gap = np.where((formed(raw) & np.isfinite(raw).all(1))[:, None], model - raw, -np.inf)
        k = gap.argmax(1)
        for edge in EDGES:
            i = np.where(gap.max(1) > edge)[0]
            buy = raw[i, k[i]] + COST
            hold = np.where(y[i] == k[i], 1 / buy - 1, -1.0)
            sell = (last[i, k[i]] - COST) / buy - 1
            sell = sell[np.isfinite(sell)]
            rows.append({"momento": name, "umbral": edge, "n": int(len(i)),
                         "roi_final": float(hold.mean()), "roi_final_ic": boot_ci(hold),
                         "roi_vender_1h": float(sell.mean()), "roi_vender_1h_ic": boot_ci(sell)})
    return rows


def run() -> dict:
    df = load()
    result = {"modelo": MODEL, "partidos": len(df), "apertura_h_mediana": float(df.open_h.median()),
              "precision": accuracy(df), "estrategias": strategies(df)}
    (PROCESSED / "polymarket_horizons.json").write_text(json.dumps(result, indent=1, ensure_ascii=False, default=float))
    return result


if __name__ == "__main__":
    pd.set_option("display.width", 220)
    r = run()
    print(f"{r['partidos']} partidos; Polymarket abre {r['apertura_h_mediana']:.0f} h antes (mediana). Modelo: {r['modelo']}")
    t = pd.DataFrame(r["precision"])
    t["ic"] = [f"[{a:+.4f}, {b:+.4f}]" if a is not None else "" for a, b in (x or (None, None) for x in t.ic)]
    print("\n== Precisión de Polymarket por momento (solo mercados formados) frente al modelo")
    print(t.round(4).to_string(index=False))
    t = pd.DataFrame(r["estrategias"])
    for c in ("roi_final_ic", "roi_vender_1h_ic"):
        t[c] = [f"[{a:+.3f}, {b:+.3f}]" for a, b in t[c]]
    print(f"\n== Comprar el Sí si modelo − precio > umbral (coste {COST} por acción)")
    print(t.round(3).to_string(index=False))
