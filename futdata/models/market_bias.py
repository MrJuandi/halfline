"""Sesgos del mercado 1X2 y estrategias a la mejor cuota, validadas por periodos.

1. Quitar el margen de la cuota media: proporcional, Shin y potencia. Log-loss y pendiente de
   calibración (logística del resultado sobre el logit de la probabilidad, todas las selecciones):
   pendiente > 1 = el mercado se queda corto en los extremos (sesgo favorito-longshot).
2. Favorito-longshot: frecuencia real frente a probabilidad sin margen, por tramos.
3. Empates: frecuencia real frente a la implícita según lo igualado del partido |p_local − p_visitante|.
4. Estrategias de apuesta plana (1 unidad) con la cuota pre-cierre de la mejor casa (Max de
   Football-Data), Bet365, Betfair Exchange (comisión del 5 % sobre la ganancia) y la media.
   Las señales usan solo la cuota media pre-cierre sin margen (Shin). Para cada familia y casa,
   el umbral se elige en descubrimiento (2021/22–2023/24, mínimo MIN_BETS apuestas), se comprueba
   en validación (2024/25) y se evalúa una vez en test (2025/26–2026/27). Betfair empieza en
   2024/25: su umbral se elige en validación. "fuera de muestra" junta los periodos posteriores
   al de elección.
   CLV: valor esperado de cada apuesta con la probabilidad de cierre (media de casas, Shin).
   Converge mucho antes que el ROI: un CLV > 0 sostenido indica información real.

Salida: data/processed/market_bias.json
Uso:    python -m futdata.models.market_bias
"""
from __future__ import annotations

import json
import logging

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

from futdata.matches import PROCESSED
from futdata.models import data
from futdata.models.evaluate import boot_ci, logloss_rows
from futdata.models.margin import power, proportional, shin

log = logging.getLogger("futdata")

LABELS = ["home", "draw", "away"]
PERIODS = {"descubrimiento": [2021, 2022, 2023], "validación": [2024], "test": [2025, 2026]}
BFE_COMMISSION = 0.05
MIN_BETS = 200
GRIDS = {
    "favorito": [0.55, 0.6, 0.65, 0.7, 0.75, 0.8],    # p del favorito (Shin) mayor que t
    "empate igualado": [0.05, 0.1, 0.15, 0.2, 0.25],  # |p_local − p_visitante| menor que t
    "valor Shin": [0.0, 0.01, 0.02, 0.03, 0.05],      # p_Shin × cuota − 1 mayor que t
}
BOOKS = {"mejor cuota": "max", "Bet365": "b365", "Betfair": "bfe", "media": "mkt"}


# ---------------------------------------------------------------- quitar el margen

METHODS = {"proporcional": proportional, "Shin": shin, "potencia": power}


def calibration_slope(p: np.ndarray, y: np.ndarray) -> float:
    """Pendiente de la logística del acierto de cada selección sobre logit(p)."""
    pf = np.clip(p.ravel(), 1e-6, 1 - 1e-6)
    x = np.log(pf / (1 - pf))[:, None]
    hit = np.eye(3)[y].ravel()
    return float(LogisticRegression(C=1e6, max_iter=1000).fit(x, hit).coef_[0, 0])


# ---------------------------------------------------------------- datos

def load() -> pd.DataFrame:
    df = data.load()
    df = df[df.season.isin(sum(PERIODS.values(), []))]
    df = df[df[[f"mkt_odds_{l}" for l in LABELS]].notna().all(1)].reset_index(drop=True)
    df["period"] = df.season.map({s: p for p, ss in PERIODS.items() for s in ss})
    return df


def odds_of(df: pd.DataFrame, prefix: str) -> np.ndarray:
    o = df[[f"{prefix}_odds_{l}" for l in LABELS]].to_numpy(float)
    o = np.where(o > 1, o, np.nan)
    return 1 + (o - 1) * (1 - BFE_COMMISSION) if prefix.startswith("bfe") else o


# ---------------------------------------------------------------- sesgos

def margin_table(df: pd.DataFrame) -> list:
    y = df.result.to_numpy()
    rows = []
    for moment, prefix in (("pre-cierre", "mkt"), ("cierre", "close")):
        o = odds_of(df, prefix)
        ok = ~np.isnan(o).any(1)
        base = logloss_rows(proportional(o[ok]), y[ok])
        for name, f in METHODS.items():
            p = f(o[ok])
            ll = logloss_rows(p, y[ok])
            for period in PERIODS:
                m = (df.period == period).to_numpy()[ok]
                d = ll[m] - base[m]
                rows.append({"momento": moment, "método": name, "periodo": period, "n": int(m.sum()),
                             "logloss": float(ll[m].mean()), "vs_proporcional": float(d.mean()),
                             "vs_ic": boot_ci(d) if name != "proporcional" else (0.0, 0.0),
                             "pendiente": calibration_slope(p[m], y[ok][m])})
    return rows


def reliability(p: np.ndarray, hit: np.ndarray, edges) -> list:
    b = pd.cut(p, edges)
    t = pd.DataFrame({"b": b, "hit": hit, "p": p}).groupby("b", observed=True).agg(
        n=("hit", "size"), freq=("hit", "mean"), p=("p", "mean"))
    out = []
    for interval, r in t.iterrows():
        se = np.sqrt(max(r.p * (1 - r.p), 1e-9) / r.n)
        out.append({"tramo": str(interval), "n": int(r.n), "freq": r.freq, "p": r.p,
                    "z": (r.freq - r.p) / se})
    return out


def longshot_table(df: pd.DataFrame, P: dict) -> dict:
    edges = [0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 1]
    hit = np.eye(3)[df.result.to_numpy()].ravel()
    return {name: reliability(p.ravel(), hit, edges) for name, p in P.items()}


def draw_tables(df: pd.DataFrame, p: np.ndarray) -> dict:
    gap = np.abs(p[:, 0] - p[:, 2])
    draw = (df.result == 1).to_numpy()
    edges = [0, 0.1, 0.2, 0.3, 0.4, 0.6, 1]
    out = {"todos": reliability_draw(gap, draw, p[:, 1], edges)}
    for period in PERIODS:
        m = (df.period == period).to_numpy()
        out[period] = reliability_draw(gap[m], draw[m], p[m, 1], edges)
    for league in sorted(df.league.unique()):
        m = (df.league == league).to_numpy() & (gap < 0.15)
        out[f"{league} igualados (<0,15)"] = {"n": int(m.sum()), "freq": float(draw[m].mean()),
                                               "p": float(p[m, 1].mean())}
    return out


def reliability_draw(gap, draw, p_draw, edges) -> list:
    t = pd.DataFrame({"b": pd.cut(gap, edges), "d": draw, "p": p_draw}).groupby("b", observed=True).agg(
        n=("d", "size"), freq=("d", "mean"), p=("p", "mean"))
    return [{"igualdad": str(i), "n": int(r.n), "freq": r.freq, "p": r.p,
             "z": (r.freq - r.p) / np.sqrt(r.p * (1 - r.p) / r.n)} for i, r in t.iterrows()]


# ---------------------------------------------------------------- estrategias

def picks(family: str, t: float, p: np.ndarray, odds: np.ndarray) -> np.ndarray:
    """Índice del resultado apostado por partido, o −1."""
    if family == "favorito":
        return np.where(p.max(1) > t, p.argmax(1), -1)
    if family == "empate igualado":
        return np.where(np.abs(p[:, 0] - p[:, 2]) < t, 1, -1)
    ev = np.nan_to_num(p * odds - 1, nan=-np.inf)
    return np.where(ev.max(1) > t, ev.argmax(1), -1)


def bet_stats(k: np.ndarray, odds: np.ndarray, y: np.ndarray, p_close: np.ndarray, mask: np.ndarray) -> dict:
    i = np.where(mask & (k >= 0))[0]
    i = i[~np.isnan(odds[i, k[i]])]
    if len(i) == 0:
        return {"n": 0}
    kk, o = k[i], odds[i, k[i]]
    profit = np.where(y[i] == kk, o - 1, -1.0)
    clv = p_close[i, kk] * o - 1
    clv = clv[~np.isnan(clv)]
    return {"n": int(len(i)), "acierto": float((y[i] == kk).mean()), "cuota_media": float(o.mean()),
            "roi": float(profit.mean()), "roi_ic": boot_ci(profit),
            "clv": float(clv.mean()), "clv_ic": boot_ci(clv)}


def strategies(df: pd.DataFrame) -> dict:
    y = df.result.to_numpy()
    p = shin(odds_of(df, "mkt"))
    close = odds_of(df, "close")
    p_close = np.full_like(close, np.nan)
    ok = ~np.isnan(close).any(1)
    p_close[ok] = shin(close[ok])
    period = df.period.to_numpy()
    grid, chosen = [], []
    for family, thresholds in GRIDS.items():
        for book, prefix in BOOKS.items():
            odds = odds_of(df, prefix)
            pick_on = "descubrimiento" if prefix != "bfe" else "validación"
            rows = []
            for t in thresholds:
                k = picks(family, t, p, odds)
                row = {"familia": family, "casa": book, "umbral": t,
                       **{per: bet_stats(k, odds, y, p_close, period == per) for per in PERIODS},
                       "fuera de muestra": bet_stats(k, odds, y, p_close, period != pick_on)}
                rows.append(row)
            grid += rows
            valid = [r for r in rows if r[pick_on].get("n", 0) >= MIN_BETS]
            if valid:
                best = max(valid, key=lambda r: r[pick_on]["roi"])
                chosen.append({**best, "elegido_en": pick_on})
    return {"rejilla": grid, "elegidas": chosen}


def run() -> dict:
    df = load()
    mkt = odds_of(df, "mkt")
    P = {name: f(mkt) for name, f in METHODS.items()}
    result = {"n": len(df), "periodos": PERIODS,
              "margen_medio": {b: float(np.nanmean((1 / odds_of(df, pre)).sum(1)) - 1)
                               for b, pre in BOOKS.items() if pre != "bfe"} |
                              {"Betfair (sin comisión)": float(np.nanmean(
                                  (1 / df[[f"bfe_odds_{l}" for l in LABELS]].to_numpy(float)).sum(1)) - 1)},
              "metodos": margin_table(df),
              "favorito_longshot": longshot_table(df, {k: P[k] for k in ("proporcional", "Shin")}),
              "empates": draw_tables(df, P["Shin"]),
              "estrategias": strategies(df)}
    (PROCESSED / "market_bias.json").write_text(json.dumps(result, indent=1, ensure_ascii=False, default=float))
    return result


def _fmt(s: dict) -> str:
    if not s.get("n"):
        return "—".ljust(44)
    return (f"n={s['n']:5d} ROI={s['roi'] * 100:+6.2f}% [{s['roi_ic'][0] * 100:+.1f},{s['roi_ic'][1] * 100:+.1f}]"
            f" CLV={s['clv'] * 100:+.2f}%")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    pd.set_option("display.width", 220)
    r = run()
    print("Margen medio pre-cierre:", json.dumps(r["margen_medio"], default=lambda x: round(x, 4)))
    print("\n== Métodos para quitar el margen (cuota media)")
    t = pd.DataFrame(r["metodos"])
    t["vs_ic"] = [f"[{lo:+.4f}, {hi:+.4f}]" for lo, hi in t.vs_ic]
    print(t.round(4).to_string(index=False))
    for name, t in r["favorito_longshot"].items():
        print(f"\n== Favorito-longshot ({name}), todas las temporadas")
        print(pd.DataFrame(t).round(3).to_string(index=False))
    print("\n== Empate según igualdad |p_local − p_visitante| (Shin), todas las temporadas")
    print(pd.DataFrame(r["empates"]["todos"]).round(3).to_string(index=False))
    for per in PERIODS:
        print(f"-- {per}")
        print(pd.DataFrame(r["empates"][per]).round(3).to_string(index=False))
    print("-- por liga, partidos igualados")
    for k, v in r["empates"].items():
        if k.endswith("(<0,15)"):
            print(f"   {k:24s} n={v['n']:4d} freq={v['freq']:.3f} p={v['p']:.3f}")
    print("\n== Estrategias elegidas (umbral fijado en el periodo indicado)")
    for c in r["estrategias"]["elegidas"]:
        print(f"{c['familia']:16s} {c['casa']:12s} t={c['umbral']:<5} ({c['elegido_en'][:5]})")
        for per in [*PERIODS, "fuera de muestra"]:
            print(f"    {per:16s} {_fmt(c[per])}")
