"""¿Ganamos a Polymarket? Comparación en los partidos con mercado 1X2 en Polymarket (2025/26 →).

1. Precisión: log-loss de Polymarket (normalizado a suma 1) frente a casas (media), Betfair
   Exchange y nuestros modelos, en dos momentos: captura pre-cierre de Football-Data y cierre.
2. Estrategia: en ese mismo momento, comprar el "Sí" de un resultado en Polymarket cuando la
   referencia (casas, Betfair o modelo) le da más probabilidad que el precio de Polymarket
   por encima de un umbral. Se mantiene hasta el final. Beneficio por 1 $ apostado:
   (1 / (precio + coste)) − 1 si acierta, −1 si no. `coste` aproxima media horquilla y
   deslizamiento (el histórico de precios no trae la horquilla real).

Requiere: python -m futdata.polymarket y python -m futdata.models.evaluate.
Uso: python -m futdata.models.vs_polymarket
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from futdata.matches import PROCESSED
from futdata.models import data
from futdata.models.evaluate import P1X2, boot_ci, logloss_rows

LABELS = ["home", "draw", "away"]
MAX_AGE_H = 6  # descarta precios de Polymarket con más de 6 h sin actualizar


def load() -> pd.DataFrame:
    df = data.load()
    pm = pd.read_parquet(PROCESSED / "polymarket.parquet").drop(columns=["league", "home", "away", "date"])
    preds = pd.read_parquet(PROCESSED / "model_predictions.parquet")
    keep = [c for c in preds if c.split("|")[0] in ("Elo ajustado", "Dixon-Coles xG/goles", "Meta logística")]
    return df.merge(pm, on="match_id").merge(preds[["match_id"] + keep], on="match_id", how="left")


def probs(df: pd.DataFrame, source: str) -> np.ndarray:
    if source.startswith("pm_"):
        raw = df[[f"{source}_{l}" for l in LABELS]].values
        return raw / raw.sum(1, keepdims=True)
    if f"{source}|p_home" in df:
        return df[[f"{source}|{c}" for c in P1X2]].values
    return df[[f"{source}_p_{l}" for l in LABELS]].values


def accuracy(df: pd.DataFrame, when: str) -> pd.DataFrame:
    sources = ({"Polymarket": "pm_pre", "Casas (media)": "mkt", "Betfair Exchange": "bfe",
                "Modelo Elo xG": "Elo ajustado", "Modelo Dixon-Coles xG": "Dixon-Coles xG/goles",
                "Meta-modelo": "Meta logística"} if when == "pre" else
               {"Polymarket": "pm_close", "Casas (media)": "close", "Betfair Exchange": "bfe_close"})
    ok = np.isfinite(np.column_stack([probs(df, s) for s in sources.values()])).all(1)
    pm_age = df[[f"pm_{when}_age_h_{l}" for l in LABELS]].max(1)
    ok &= (pm_age <= MAX_AGE_H).values
    d, y = df[ok], df.result[ok].values
    base = logloss_rows(probs(d, sources["Polymarket"]), y)
    rows = []
    for name, s in sources.items():
        ll = logloss_rows(probs(d, s), y)
        lo, hi = boot_ci(ll - base)
        rows.append({"fuente": name, "n": int(ok.sum()), "logloss": ll.mean(), "vs_polymarket": (ll - base).mean(),
                     "ic_lo": lo, "ic_hi": hi})
    return pd.DataFrame(rows)


def strategy(df: pd.DataFrame, when: str, ref: str, edge: float, cost: float) -> dict:
    price = df[[f"pm_{when}_{l}" for l in LABELS]].values
    age = df[[f"pm_{when}_age_h_{l}" for l in LABELS]].values
    p = probs(df, ref)
    ok = np.isfinite(p).all(1) & np.isfinite(price).all(1) & (age <= MAX_AGE_H).all(1)
    gap = np.where(ok[:, None], p - (price + cost), -np.inf)
    pick = gap.argmax(1)
    sel = gap.max(1) > edge
    i = np.flatnonzero(sel)
    buy = price[i, pick[i]] + cost
    win = df.result.values[i] == pick[i]
    profit = np.where(win, 1 / buy - 1, -1.0)
    if len(i) == 0:
        return {"apuestas": 0}
    lo, hi = boot_ci(profit)
    return {"apuestas": int(len(i)), "acierto": float(win.mean()), "precio_medio": float(buy.mean()),
            "roi": float(profit.mean()), "roi_ic_lo": lo, "roi_ic_hi": hi}


def run() -> dict:
    df = load()
    acc = {when: accuracy(df, when) for when in ("pre", "close")}
    strat = []
    refs = {"pre": {"Casas (media)": "mkt", "Betfair Exchange": "bfe", "Modelo Elo xG": "Elo ajustado",
                    "Meta-modelo": "Meta logística"},
            "close": {"Casas (media)": "close", "Betfair Exchange": "bfe_close"}}
    for when, rr in refs.items():
        for name, ref in rr.items():
            for edge in (0.02, 0.04, 0.06):
                for cost in (0.0, 0.01):
                    strat.append({"momento": when, "referencia": name, "umbral": edge, "coste": cost,
                                  **strategy(df, when, ref, edge, cost)})
    strat = pd.DataFrame(strat)
    info = {"partidos_polymarket": int(len(df)), "por_liga": df.league.value_counts().to_dict(),
            "volumen_mediano": float(df.pm_volume.median()), "con_comisiones": int(df.pm_fees.sum())}
    (PROCESSED / "polymarket_report.json").write_text(json.dumps(
        {"info": info, "precision": {k: v.to_dict("records") for k, v in acc.items()},
         "estrategias": strat.to_dict("records")}, indent=1, default=float))
    return {"info": info, "acc": acc, "strat": strat}


if __name__ == "__main__":
    pd.set_option("display.width", 200)
    r = run()
    print(r["info"])
    for when, t in r["acc"].items():
        print(f"\n== Precisión ({when})")
        print(t.round(4).to_string(index=False))
    print("\n== Estrategias en Polymarket")
    print(r["strat"].round(3).to_string(index=False))
