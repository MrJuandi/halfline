"""Sesgos de los mercados de más/menos 2,5 goles y hándicap asiático, con el protocolo del 1X2.

Mismo protocolo que futdata/models/market_bias.py (ver docs/sesgos_mercado.md):

1. Quitar el margen de la cuota media (proporcional, Shin y potencia). Log-loss y pendiente de
   calibración por periodos.
2. Sesgos: en más/menos, frecuencia real de más de 2,5 frente a la implícita por tramo, liga y
   periodo; en hándicap, si el favorito con la línea (el que da goles) cubre más o menos de lo implícito.
3. Estrategias de apuesta plana (1 unidad) a la cuota pre-cierre de la mejor casa (Max), Bet365,
   Betfair Exchange (comisión del 5 % sobre la ganancia) y la media. Umbral elegido en
   descubrimiento (2021/22–2023/24; Betfair y el modelo, que empiezan más tarde, ver abajo),
   comprobado en validación (2024/25) y evaluado en test (2025/26–2026/27). ROI con bootstrap y
   CLV con la cuota media de cierre sin margen.
   En más/menos se incluye el modelo Dixon-Coles xG/goles (p_over de model_predictions.parquet,
   walk-forward desde 2022/23) frente al mercado.

Hándicap asiático. La línea AHh de Football-Data es el hándicap del local (−0,75: el local da 0,75
goles). Liquidación (ah_split): líneas enteras con push = devolución, líneas de .5 sin push y líneas
de cuarto partidas en dos medias apuestas (−0,75 = mitad a −0,5 y mitad a −1). Con fracciones
ganada w y perdida l de la apuesta, el beneficio a cuota o es w·(o − 1) − l y la probabilidad
sin margen que hace la apuesta justa es w/(w + l). Por eso la calibración y el log-loss usan como
resultado y = w/(w + l) (siempre 0 o 1) con peso w + l (1, 0,5 en medio push, 0 en push).
La cuota de cierre solo sirve de CLV si la línea de cierre (AHCh) es la misma; si no, se registra
si la línea se movió a favor o en contra de la apuesta.

Salida: data/processed/market_bias_goals.json
Uso:    python -m futdata.models.market_bias_goals
"""
from __future__ import annotations

import json
import logging

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

from futdata.common import RAW, fd_code
from futdata.matches import PROCESSED
from futdata.models.evaluate import boot_ci
from futdata.models.margin import power, proportional, shin

log = logging.getLogger("futdata")

PERIODS = {"descubrimiento": [2021, 2022, 2023], "validación": [2024], "test": [2025, 2026]}
BFE_COMMISSION = 0.05
MIN_BETS = 200
MAX_OVER_AVG = 1.25
METHODS = {"proporcional": proportional, "Shin": shin, "potencia": power}
BOOKS = {"mejor cuota": "max", "Bet365": "b365", "Betfair": "bfe", "media": "mkt"}
DC = "Dixon-Coles xG/goles"

COLUMNS = {  # mercado -> prefijo -> columnas de Football-Data (más/local, menos/visitante)
    "ou": {"mkt": ("Avg>2.5", "Avg<2.5"), "close": ("AvgC>2.5", "AvgC<2.5"),
           "max": ("Max>2.5", "Max<2.5"), "b365": ("B365>2.5", "B365<2.5"),
           "bfe": ("BFE>2.5", "BFE<2.5")},
    "ah": {"mkt": ("AvgAHH", "AvgAHA"), "close": ("AvgCAHH", "AvgCAHA"),
           "max": ("MaxAHH", "MaxAHA"), "b365": ("B365AHH", "B365AHA"),
           "bfe": ("BFEAHH", "BFEAHA")},
}
LINES = {"ah_line": "AHh", "ah_close_line": "AHCh"}

GRIDS = {
    "ou": {
        "más": [0.5, 0.55, 0.6, 0.65, 0.7],            # p_más (potencia) mayor que t
        "menos": [0.35, 0.4, 0.45, 0.5, 0.55],         # p_más menor que t: apostar a menos
        "valor": [0.0, 0.01, 0.02, 0.03, 0.05],        # p × cuota − 1 mayor que t
        "DC diferencia": [0.02, 0.04, 0.06, 0.08, 0.1],  # |p_modelo − p_mercado| mayor que t
        "DC valor": [0.0, 0.02, 0.04, 0.06, 0.08],     # p_modelo × cuota − 1 mayor que t
    },
    "ah": {
        "favorito": [0.25, 0.5, 0.75, 1.0, 1.5],       # |línea| ≥ t: apostar al que da goles
        "no favorito": [0.25, 0.5, 0.75, 1.0, 1.5],    # |línea| ≥ t: apostar al que los recibe
        "valor": [0.0, 0.01, 0.02, 0.03, 0.05],
    },
}


# ---------------------------------------------------------------- liquidación del hándicap asiático

def ah_split(line, diff) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Fracción de la apuesta (ganada, devuelta, perdida) para quien recibe `line` goles con
    diferencia de goles `diff` (sus goles − los del rival). Las líneas de cuarto (±0,25, ±0,75…)
    se parten en dos medias apuestas a la línea ±0,25."""
    line, diff = np.asarray(line, float), np.asarray(diff, float)
    quarter = np.isclose(np.mod(line * 4, 2), 1)
    win = push = lose = 0.0
    for half in (np.where(quarter, line - 0.25, line), np.where(quarter, line + 0.25, line)):
        m = diff + half
        win = win + 0.5 * (m > 0)
        push = push + 0.5 * (m == 0)
        lose = lose + 0.5 * (m < 0)
    return win, push, lose


def ah_profit(line, diff, odds) -> np.ndarray:
    """Beneficio de 1 unidad apostada a cuota `odds`."""
    win, _, lose = ah_split(line, diff)
    return win * (np.asarray(odds, float) - 1) - lose


# ---------------------------------------------------------------- datos

def load() -> pd.DataFrame:
    """Un partido por fila con goles, cuotas de más/menos 2,5 y hándicap asiático, y p_más del modelo."""
    matches = pd.read_parquet(PROCESSED / "matches.parquet")
    matches = matches[matches.season.isin(sum(PERIODS.values(), [])) & matches.home_goals.notna()]
    parts = []
    for (league, season), g in matches.groupby(["league", "season"]):
        csv = pd.read_csv(RAW / "football_data" / fd_code(season) / f"{league}.csv",
                          encoding="latin-1", on_bad_lines="skip")
        src = csv.loc[g.fd_row.values].reset_index(drop=True)
        out = g[["match_id", "league", "season", "home_goals", "away_goals"]].reset_index(drop=True)
        for market, books in COLUMNS.items():
            for prefix, cols in books.items():
                for side, c in zip((0, 1), cols):
                    out[f"{market}_{prefix}_{side}"] = (pd.to_numeric(src[c], errors="coerce")
                                                        if c in src else np.nan)
        for name, c in LINES.items():
            out[name] = pd.to_numeric(src[c], errors="coerce") if c in src else np.nan
        parts.append(out)
    df = pd.concat(parts, ignore_index=True)
    df["period"] = df.season.map({s: p for p, ss in PERIODS.items() for s in ss})
    df["diff"] = df.home_goals - df.away_goals
    df["over"] = (df.home_goals + df.away_goals > 2.5).astype(int)
    pred = pd.read_parquet(PROCESSED / "model_predictions.parquet", columns=["match_id", f"{DC}|p_over"])
    return df.merge(pred.rename(columns={f"{DC}|p_over": "dc_p_over"}), on="match_id", how="left")


def raw_odds(df: pd.DataFrame, market: str, prefix: str) -> np.ndarray:
    o = df[[f"{market}_{prefix}_0", f"{market}_{prefix}_1"]].to_numpy(float)
    return np.where(o > 1, o, np.nan)


def odds_of(df: pd.DataFrame, market: str, prefix: str) -> np.ndarray:
    """Cuotas (n, 2) con limpieza de errores de Football-Data (en 2025/26 hay ~40 partidos con una
    casa a 22,00 en el hándicap, que contamina también la media):
    - media y cierre: sin margen positivo (suma de 1/cuota < 1) la fila no es creíble → NaN;
    - mejor cuota: más de un 25 % por encima de la media → NaN (la cuota no era alcanzable).
    Betfair: cuota neta de la comisión del 5 % sobre la ganancia."""
    o = raw_odds(df, market, prefix)
    if prefix in ("mkt", "close"):
        o[(1 / o).sum(1) < 1] = np.nan
    if prefix == "max":
        avg = odds_of(df, market, "mkt")
        o[np.isnan(avg) | (o > MAX_OVER_AVG * avg)] = np.nan
    return 1 + (o - 1) * (1 - BFE_COMMISSION) if prefix == "bfe" else o


def fair_of(odds: np.ndarray, f=power) -> np.ndarray:
    out = np.full(odds.shape, np.nan)
    ok = ~np.isnan(odds).any(1)
    if ok.any():
        out[ok] = f(odds[ok])
    return out


def outcomes(df: pd.DataFrame, market: str) -> tuple[np.ndarray, np.ndarray]:
    """Fracciones ganada W y perdida L de cada selección (n, 2): más/menos o local/visitante."""
    if market == "ou":
        W = np.column_stack([df.over, 1 - df.over]).astype(float)
        return W, 1 - W
    line, diff = df.ah_line.to_numpy(float), df["diff"].to_numpy(float)
    wh, _, lh = ah_split(line, diff)
    wa, _, la = ah_split(-line, -diff)
    return np.column_stack([wh, wa]), np.column_stack([lh, la])


def target(df: pd.DataFrame, market: str) -> tuple[np.ndarray, np.ndarray]:
    """Resultado binario de la primera selección (más / local) y su peso (parte no devuelta)."""
    W, L = outcomes(df, market)
    w = W[:, 0] + L[:, 0]
    y = np.divide(W[:, 0], w, out=np.zeros_like(w), where=w > 0)
    return y, w


def subset(df: pd.DataFrame, market: str) -> pd.DataFrame:
    m = ~np.isnan(odds_of(df, market, "mkt")).any(1)
    if market == "ah":
        m &= df.ah_line.notna().to_numpy()
    return df[m].reset_index(drop=True)


# ---------------------------------------------------------------- quitar el margen

def calibration_slope(p: np.ndarray, y: np.ndarray, w: np.ndarray) -> float:
    """Pendiente de la logística (ponderada) del acierto de las dos selecciones sobre logit(p)."""
    pf = np.clip(np.concatenate([p, 1 - p]), 1e-6, 1 - 1e-6)
    x = np.log(pf / (1 - pf))[:, None]
    hit = np.concatenate([y, 1 - y])
    return float(LogisticRegression(C=1e6, max_iter=1000).fit(
        x, hit, sample_weight=np.concatenate([w, w])).coef_[0, 0])


def logloss_bin(p: np.ndarray, y: np.ndarray) -> np.ndarray:
    p = np.clip(p, 1e-12, 1 - 1e-12)
    return -(y * np.log(p) + (1 - y) * np.log(1 - p))


def wmean_ci(x: np.ndarray, w: np.ndarray) -> tuple[float, float]:
    """Intervalo bootstrap de la media ponderada sum(w·x)/sum(w) (aproximado por w·x/media(w))."""
    return boot_ci(w * x / w.mean())


def margin_table(df: pd.DataFrame, market: str) -> list:
    y, w = target(df, market)
    period = df.period.to_numpy()
    rows = []
    for moment, prefix in (("pre-cierre", "mkt"), ("cierre", "close")):
        o = odds_of(df, market, prefix)
        ok = ~np.isnan(o).any(1) & (w > 0)
        if market == "ah" and prefix == "close":
            ok &= (df.ah_close_line == df.ah_line).to_numpy()  # la cuota de cierre es de otra línea
        base = logloss_bin(proportional(o[ok])[:, 0], y[ok])
        for name, f in METHODS.items():
            p = f(o[ok])[:, 0]
            ll = logloss_bin(p, y[ok])
            for per in PERIODS:
                m = period[ok] == per
                ww, d = w[ok][m], ll[m] - base[m]
                rows.append({"momento": moment, "método": name, "periodo": per, "n": int(m.sum()),
                             "logloss": float(np.average(ll[m], weights=ww)),
                             "vs_proporcional": float(np.average(d, weights=ww)),
                             "vs_ic": wmean_ci(d, ww) if name != "proporcional" else (0.0, 0.0),
                             "sesgo_primera": float(np.average(y[ok][m] - p[m], weights=ww)),
                             "pendiente": calibration_slope(p[m], y[ok][m], ww)})
    return rows


def margins(df: pd.DataFrame, market: str) -> dict:
    out = {b: float(np.nanmean((1 / odds_of(df, market, pre)).sum(1)) - 1)
           for b, pre in BOOKS.items() if pre != "bfe"}
    out["Betfair (sin comisión)"] = float(np.nanmean((1 / raw_odds(df, market, "bfe")).sum(1)) - 1)
    return out


# ---------------------------------------------------------------- sesgos

def reliability(groups, y: np.ndarray, p: np.ndarray, w: np.ndarray, key: str = "tramo") -> list:
    t = pd.DataFrame({"g": groups, "wy": w * y, "wp": w * p, "w": w}).groupby("g", observed=True, sort=True)
    t = t.agg(n=("w", "size"), peso=("w", "sum"), wy=("wy", "sum"), wp=("wp", "sum"))
    out = []
    for g, r in t.iterrows():
        if r.peso <= 0:
            continue
        freq, pm = r.wy / r.peso, r.wp / r.peso
        out.append({key: str(g), "n": int(r.n), "peso": float(r.peso), "freq": float(freq), "p": float(pm),
                    "z": float((freq - pm) / np.sqrt(max(pm * (1 - pm), 1e-9) / r.peso))})
    return out


def ou_biases(df: pd.DataFrame) -> dict:
    p = fair_of(odds_of(df, "ou", "mkt"))[:, 0]
    y, w = df.over.to_numpy(float), np.ones(len(df))
    edges = [0, 0.4, 0.45, 0.5, 0.55, 0.6, 0.65, 0.7, 1]
    out = {"tramos": reliability(pd.cut(p, edges), y, p, w),
           "por_liga": reliability(df.league.to_numpy(), y, p, w, "liga"),
           "por_periodo": reliability(df.period.to_numpy(), y, p, w, "periodo")}
    for per in PERIODS:
        m = (df.period == per).to_numpy()
        out[f"tramos {per}"] = reliability(pd.cut(p[m], edges), y[m], p[m], w[m])
        out[f"por_liga {per}"] = reliability(df.league.to_numpy()[m], y[m], p[m], w[m], "liga")
    return out


def ah_favourite(df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Para cada partido con línea ≠ 0: índice del favorito (0 local, 1 visitante), su p sin margen,
    su resultado binario y el peso. NaN/−1 si la línea es 0."""
    line = df.ah_line.to_numpy(float)
    k = np.where(line < 0, 0, np.where(line > 0, 1, -1))
    p = fair_of(odds_of(df, "ah", "mkt"))
    y, w = target(df, "ah")
    kk = np.maximum(k, 0)
    p_fav = np.where(kk == 0, p[:, 0], p[:, 1])
    y_fav = np.where(kk == 0, y, 1 - y)
    return k, p_fav, y_fav, w


def ah_biases(df: pd.DataFrame) -> dict:
    k, p_fav, y_fav, w = ah_favourite(df)
    line = df.ah_line.to_numpy(float)
    m = (k >= 0) & (w > 0)
    absl = np.abs(line)
    size = np.select([absl <= 0.25, absl <= 0.5, absl <= 0.75, absl <= 1, absl <= 1.5],
                     ["0,25", "0,5", "0,75", "1", "1,25–1,5"], "≥ 1,75")
    kind = np.select([np.isclose(np.mod(line * 4, 2), 1), np.isclose(np.mod(line, 1), 0.5)],
                     ["cuarto", "media"], "entera")
    p_home = fair_of(odds_of(df, "ah", "mkt"))[:, 0]
    y, wh = target(df, "ah")
    out = {"favorito_por_linea": reliability(size[m], y_fav[m], p_fav[m], w[m], "|línea|"),
           "favorito_por_tipo": reliability(kind[m], y_fav[m], p_fav[m], w[m], "tipo"),
           "favorito_por_liga": reliability(df.league.to_numpy()[m], y_fav[m], p_fav[m], w[m], "liga"),
           "favorito_por_periodo": reliability(df.period.to_numpy()[m], y_fav[m], p_fav[m], w[m], "periodo"),
           "local_por_periodo": reliability(df.period.to_numpy()[wh > 0], y[wh > 0], p_home[wh > 0],
                                            wh[wh > 0], "periodo"),
           "favorito_tramos_p": reliability(pd.cut(p_fav[m], [0, 0.45, 0.5, 0.55, 1]), y_fav[m], p_fav[m], w[m]),
           "linea_cierre": {"n": int(df.ah_close_line.notna().sum()),
                            "igual": float((df.ah_close_line == df.ah_line).mean())}}
    for per in PERIODS:
        mp = m & (df.period == per).to_numpy()
        out[f"favorito_por_linea {per}"] = reliability(size[mp], y_fav[mp], p_fav[mp], w[mp], "|línea|")
    return out


# ---------------------------------------------------------------- estrategias

def picks(family: str, t: float, p: np.ndarray, odds: np.ndarray, line=None, p_model=None) -> np.ndarray:
    """Índice de la selección apostada por partido (0 más/local, 1 menos/visitante), o −1.
    p: probabilidades sin margen del mercado medio pre-cierre (n, 2)."""
    if family == "más":
        return np.where(p[:, 0] > t, 0, -1)
    if family == "menos":
        return np.where(p[:, 0] < t, 1, -1)
    if family in ("favorito", "no favorito"):
        line = np.asarray(line, float)
        fav = np.where(line < 0, 0, 1)
        side = fav if family == "favorito" else 1 - fav
        return np.where((np.abs(line) >= t) & (line != 0), side, -1)
    if family == "DC diferencia":
        d = np.nan_to_num(np.asarray(p_model, float) - p[:, 0])
        return np.where(d > t, 0, np.where(d < -t, 1, -1))
    q = p
    if family == "DC valor":
        pm = np.asarray(p_model, float)
        q = np.column_stack([pm, 1 - pm])
    elif family != "valor":
        raise ValueError(family)
    ev = np.nan_to_num(q * odds - 1, nan=-np.inf)
    return np.where(ev.max(1) > t, ev.argmax(1), -1)


def bet_stats(k, odds, W, L, p_close, clv_ok, moved, mask) -> dict:
    i = np.where(mask & (k >= 0))[0]
    i = i[~np.isnan(odds[i, k[i]])]
    if len(i) == 0:
        return {"n": 0}
    kk, o = k[i], odds[i, k[i]]
    profit = W[i, kk] * (o - 1) - L[i, kk]
    clv = (p_close[i, kk] * o - 1)[clv_ok[i]]
    clv = clv[~np.isnan(clv)]
    out = {"n": int(len(i)), "acierto": float((W[i, kk] > L[i, kk]).mean()), "cuota_media": float(o.mean()),
           "roi": float(profit.mean()), "roi_ic": boot_ci(profit),
           "clv_n": int(len(clv)),
           "clv": float(clv.mean()) if len(clv) else None,
           "clv_ic": boot_ci(clv) if len(clv) > 1 else None}
    if moved is not None:  # hándicap: +1 la línea de cierre se movió a favor de la apuesta, −1 en contra
        mv = moved[i, kk]
        out["linea_a_favor"] = float((mv > 0).mean())
        out["linea_en_contra"] = float((mv < 0).mean())
    return out


def strategies(df: pd.DataFrame, market: str) -> dict:
    W, L = outcomes(df, market)
    p = fair_of(odds_of(df, market, "mkt"))
    p_close = fair_of(odds_of(df, market, "close"))
    period = df.period.to_numpy()
    line = df.ah_line.to_numpy(float) if market == "ah" else None
    if market == "ah":
        close_line = df.ah_close_line.to_numpy(float)
        clv_ok = close_line == line
        # local: línea de cierre más negativa = el mercado lo ve más fuerte = a favor del que apostó al local
        mv = np.sign(line - close_line)
        moved = np.nan_to_num(np.column_stack([mv, -mv]))
    else:
        clv_ok, moved = np.ones(len(df), bool), None
    p_model = df.dc_p_over.to_numpy(float)
    model_seasons = sorted(df.season[df.dc_p_over.notna()].unique())
    grid, chosen = [], []
    for family, thresholds in GRIDS[market].items():
        for book, prefix in BOOKS.items():
            odds = odds_of(df, market, prefix)
            pick_on = "validación" if prefix == "bfe" else "descubrimiento"
            rows = []
            for t in thresholds:
                k = picks(family, t, p, odds, line, p_model)
                row = {"familia": family, "casa": book, "umbral": t,
                       **{per: bet_stats(k, odds, W, L, p_close, clv_ok, moved, period == per) for per in PERIODS},
                       "fuera de muestra": bet_stats(k, odds, W, L, p_close, clv_ok, moved, period != pick_on)}
                rows.append(row)
            grid += rows
            valid = [r for r in rows if r[pick_on].get("n", 0) >= MIN_BETS]
            if valid:
                best = max(valid, key=lambda r: r[pick_on]["roi"])
                chosen.append({**best, "elegido_en": pick_on})
    return {"rejilla": grid, "elegidas": chosen,
            "temporadas_modelo": [int(s) for s in model_seasons] if market == "ou" else None}


def model_vs_market(df: pd.DataFrame) -> list:
    """Log-loss del modelo Dixon-Coles xG/goles en más/menos frente al mercado (potencia), por periodo."""
    m = df.dc_p_over.notna().to_numpy()
    y = df.over.to_numpy(float)[m]
    pm = fair_of(odds_of(df, "ou", "mkt"))[m, 0]
    pc = fair_of(odds_of(df, "ou", "close"))[m, 0]
    pd_ = df.dc_p_over.to_numpy(float)[m]
    out = []
    for per in PERIODS:
        mp = (df.period.to_numpy()[m] == per) & ~np.isnan(pc)
        if not mp.any():
            continue
        d = logloss_bin(pd_[mp], y[mp]) - logloss_bin(pm[mp], y[mp])
        out.append({"periodo": per, "n": int(mp.sum()),
                    "modelo": float(logloss_bin(pd_[mp], y[mp]).mean()),
                    "mercado": float(logloss_bin(pm[mp], y[mp]).mean()),
                    "cierre": float(logloss_bin(pc[mp], y[mp]).mean()),
                    "modelo_menos_mercado": float(d.mean()), "ic": boot_ci(d),
                    "corr_modelo_mercado": float(np.corrcoef(pd_[mp], pm[mp])[0, 1])})
    return out


def run() -> dict:
    df = load()
    result = {"periodos": PERIODS}
    for market, name in (("ou", "más/menos 2,5"), ("ah", "hándicap asiático")):
        d = subset(df, market)
        log.info("%s: %d partidos", name, len(d))
        result[name] = {"n": len(d), "n_por_periodo": d.period.value_counts().to_dict(),
                        "margen_medio": margins(d, market),
                        "metodos": margin_table(d, market),
                        "sesgos": ou_biases(d) if market == "ou" else ah_biases(d),
                        "estrategias": strategies(d, market)}
        if market == "ou":
            result[name]["modelo_vs_mercado"] = model_vs_market(d)
    (PROCESSED / "market_bias_goals.json").write_text(
        json.dumps(result, indent=1, ensure_ascii=False, default=float))
    return result


def _fmt(s: dict) -> str:
    if not s.get("n"):
        return "—".ljust(44)
    out = f"n={s['n']:5d} ROI={s['roi'] * 100:+6.2f}% [{s['roi_ic'][0] * 100:+.1f},{s['roi_ic'][1] * 100:+.1f}]"
    if s.get("clv") is not None:
        out += f" CLV={s['clv'] * 100:+.2f}% (n={s['clv_n']})"
    if "linea_a_favor" in s:
        out += f" línea +{s['linea_a_favor'] * 100:.0f}%/−{s['linea_en_contra'] * 100:.0f}%"
    return out


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    pd.set_option("display.width", 220)
    r = run()
    for name in ("más/menos 2,5", "hándicap asiático"):
        R = r[name]
        print(f"\n######## {name}: {R['n']} partidos {R['n_por_periodo']}")
        print("Margen medio pre-cierre:", json.dumps(R["margen_medio"], default=lambda x: round(x, 4)))
        print("\n== Métodos para quitar el margen")
        t = pd.DataFrame(R["metodos"])
        t["vs_ic"] = [f"[{lo:+.4f}, {hi:+.4f}]" for lo, hi in t.vs_ic]
        print(t.round(4).to_string(index=False))
        for k, v in R["sesgos"].items():
            print(f"\n== {k}")
            print(pd.DataFrame(v if isinstance(v, list) else [v]).round(3).to_string(index=False))
        if "modelo_vs_mercado" in R:
            print("\n== Dixon-Coles xG/goles frente al mercado (log-loss más/menos)")
            print(pd.DataFrame(R["modelo_vs_mercado"]).round(4).to_string(index=False))
        print("\n== Estrategias elegidas")
        for c in R["estrategias"]["elegidas"]:
            print(f"{c['familia']:14s} {c['casa']:12s} t={c['umbral']:<5} ({c['elegido_en'][:5]})")
            for per in [*PERIODS, "fuera de muestra"]:
                print(f"    {per:16s} {_fmt(c[per])}")
