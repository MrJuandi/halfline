"""Banco de evaluación de modelos frente al mercado.

Protocolo:
  - Validación: 2024/25. Ahí se eligen los hiperparámetros de cada familia.
  - Test: 2025/26 y 2026/27 (en curso). Se evalúa una sola vez con lo elegido en validación.
  - Modelos de goles: re-ajuste semanal con los partidos anteriores (walk-forward).
  - Ratings y meta-modelos: la capa que convierte variables en probabilidades se entrena con
    las temporadas anteriores a la que se predice (ventana creciente desde 2022/23).
  - 2021/22 es calentamiento: no se predice.
Métricas: log-loss, RPS y Brier (1X2); log-loss más/menos 2,5. Diferencia frente al mercado
pre-cierre con intervalo bootstrap al 95 % (emparejado por partido), también desglosada en partidos
igualados (favorito del mercado < 40 %) y con algún ascendido.

Mejoras para empates y ascendidos (docs/modelos.md, sección 9):
  - Dixon-Coles inflado en empates (goals.probs, `draw_inflation`).
  - Capa de empate: logística multinomial con la diferencia de Elo, su valor absoluto o cuadrado
    (igualdad) y los goles totales esperados por Dixon-Coles, en lugar de la logística de una variable.
  - Elo con rating inicial de ascendidos según su valor de plantilla (squads.py).

Salida: data/processed/model_predictions.parquet y data/processed/model_report.json
Uso:    python -m futdata.models.evaluate
"""
from __future__ import annotations

import itertools
import json
import logging

import numpy as np
import pandas as pd
from joblib import Parallel, delayed
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from futdata.matches import PROCESSED
from futdata.models import data, goals, lineups, ratings, squads

log = logging.getLogger("futdata")

VAL, TEST = [2024], [2025, 2026]
DRAW_SETS = {"r, |r|": ["r", "abs_r"], "r, r²": ["r", "r2"],
             "r, |r|, goles": ["r", "abs_r", "tot"], "r, r², goles": ["r", "r2", "tot"]}
INFLATION = (0.0, 0.05, 0.1, 0.15, 0.2)
FIRST_PRED = 2022
P1X2 = ["p_home", "p_draw", "p_away"]
EPS = 1e-12


# ---------------------------------------------------------------- métricas

def logloss_rows(p: np.ndarray, y: np.ndarray) -> np.ndarray:
    return -np.log(np.clip(p[np.arange(len(y)), y], EPS, 1))


def rps_rows(p: np.ndarray, y: np.ndarray) -> np.ndarray:
    o = np.eye(3)[y]
    return 0.5 * ((p[:, 0] - o[:, 0]) ** 2 + (p[:, :2].sum(1) - o[:, :2].sum(1)) ** 2)


def brier_rows(p: np.ndarray, y: np.ndarray) -> np.ndarray:
    return ((p - np.eye(3)[y]) ** 2).sum(1)


def binary_logloss_rows(p: np.ndarray, y: np.ndarray) -> np.ndarray:
    p = np.clip(p, EPS, 1 - EPS)
    return -(y * np.log(p) + (1 - y) * np.log(1 - p))


def boot_ci(x: np.ndarray, n: int = 2000, seed: int = 0) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    means = x[rng.integers(0, len(x), (n, len(x)))].mean(1)
    return float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


# ---------------------------------------------------------------- capa de probabilidad

def logits(p: np.ndarray) -> np.ndarray:
    """(n, 3) -> log(p_local/p_empate), log(p_visitante/p_empate)."""
    p = np.clip(p, 1e-6, 1)
    return np.column_stack([np.log(p[:, 0] / p[:, 1]), np.log(p[:, 2] / p[:, 1])])


def expanding(df: pd.DataFrame, X: pd.DataFrame, make_model, seasons: list[int]) -> pd.DataFrame:
    """Para cada temporada a predecir, entrena con las anteriores (desde FIRST_PRED)."""
    out = pd.DataFrame(index=df.index, columns=P1X2, dtype=float)
    for s in seasons:
        tr = (df.season >= FIRST_PRED) & (df.season < s) & X.notna().all(1)
        te = (df.season == s)
        if not tr.any():
            continue
        model = make_model().fit(X[tr], df.result[tr])
        out.loc[te] = model.predict_proba(X[te].fillna(X[tr].mean()))
    return out


def logistic():
    return make_pipeline(StandardScaler(), LogisticRegression(C=1.0, max_iter=2000))


def score(df: pd.DataFrame, p: pd.DataFrame, mask: pd.Series) -> float:
    return float(logloss_rows(p.loc[mask, P1X2].values, df.result[mask].values).mean())


# ---------------------------------------------------------------- búsqueda en validación

def tune_goals(df: pd.DataFrame) -> dict:
    val = df.season.isin(VAL)
    grid = list(itertools.product([0.0, 0.25, 0.5, 0.75, 1.0], [90, 180, 365, 730], [1e-3, 1e-2]))
    rows = []
    for gw, hl, alpha in grid:
        lam = goals.lambdas(df, val, goal_weight=gw, half_life=hl, alpha=alpha)
        for rho, infl in itertools.product((-0.15, -0.1, -0.05, 0.0, 0.05), INFLATION):
            p = goals.probs(lam, rho, infl)
            ll = logloss_rows(p[P1X2].values, df.result[val].values).mean()
            ou = binary_logloss_rows(p.p_over.values, df.over[val].values).mean()
            rows.append({"goal_weight": gw, "half_life": hl, "alpha": alpha, "rho": rho,
                         "draw_inflation": infl, "ll": ll, "ou": ou})
        log.info("goles gw=%s hl=%s alpha=%s: %.4f", gw, hl, alpha,
                 min(r["ll"] for r in rows[-5 * len(INFLATION):]))
    res = pd.DataFrame(rows)
    plain = res[res.draw_inflation == 0]
    return {"table": res, "best": plain.loc[plain.ll.idxmin()].to_dict(),
            "best_goals_only": plain[plain.goal_weight == 1].loc[lambda r: r.ll.idxmin()].to_dict(),
            "best_inflated": res[res.draw_inflation > 0].loc[lambda r: r.ll.idxmin()].to_dict()}


def _rating_score(df, feature: pd.Series) -> float:
    X = feature.to_frame("r")
    p = expanding(df, X, logistic, VAL)
    return score(df, p, df.season.isin(VAL))


def tune_elo(df: pd.DataFrame) -> pd.DataFrame:
    grid = list(itertools.product([10, 20, 30, 40], [40, 70], [1500, 1400, 1350], [0.0, 0.5, 1.0]))
    feats = Parallel(n_jobs=-1)(delayed(ratings.elo)(df, k=k, home=h, start_new=sn, xg_weight=xw)
                                for k, h, sn, xw in grid)
    rows = [{"k": k, "home": h, "start_new": sn, "xg_weight": xw, "ll": _rating_score(df, f)}
            for (k, h, sn, xw), f in zip(grid, feats)]
    return pd.DataFrame(rows).sort_values("ll")


def tune_pi(df: pd.DataFrame) -> pd.DataFrame:
    grid = list(itertools.product([0.02, 0.035, 0.06, 0.1], [0.5, 0.7, 0.9], [0.0, 0.5, 1.0]))
    feats = Parallel(n_jobs=-1)(delayed(ratings.pi_ratings)(df, lam=l, gamma=g, xg_weight=xw)
                                for l, g, xw in grid)
    rows = [{"lam": l, "gamma": g, "xg_weight": xw, "ll": _rating_score(df, f)}
            for (l, g, xw), f in zip(grid, feats)]
    return pd.DataFrame(rows).sort_values("ll")


def tune_squad(df: pd.DataFrame, best_e: dict, squad: dict) -> pd.DataFrame:
    """Peso del valor de plantilla en el rating inicial de los ascendidos (resto, como el Elo ajustado)."""
    weights = [0.25, 0.5, 0.75, 1.0]
    feats = Parallel(n_jobs=-1)(delayed(ratings.elo)(
        df, k=best_e["k"], home=best_e["home"], start_new=best_e["start_new"], xg_weight=best_e["xg_weight"],
        squad=squad, value_weight=w) for w in weights)
    return pd.DataFrame([{"value_weight": w, "ll": _rating_score(df, f)}
                         for w, f in zip(weights, feats)]).sort_values("ll")


def draw_features(r: pd.Series, lam: pd.DataFrame) -> pd.DataFrame:
    """Capa de empate: diferencia de Elo, medidas de igualdad (|r| y r², en centenas de puntos) y log de
    los goles totales que espera Dixon-Coles (con menos goles, más empates)."""
    lam = lam.reindex(r.index)
    return pd.DataFrame({"r": r, "abs_r": r.abs() / 100, "r2": (r / 100) ** 2,
                         "tot": np.log(lam.lam_home + lam.lam_away)}, index=r.index)


def tune_draw(df: pd.DataFrame, X: pd.DataFrame) -> pd.DataFrame:
    val = df.season.isin(VAL)
    return pd.DataFrame([{"variables": name, "ll": score(df, expanding(df, X[cols], logistic, VAL), val)}
                         for name, cols in DRAW_SETS.items()]).sort_values("ll")


# ---------------------------------------------------------------- informe

def report(df: pd.DataFrame, preds: dict[str, pd.DataFrame], mask: pd.Series) -> pd.DataFrame:
    y = df.result[mask].values
    mkt = df.loc[mask, ["mkt_p_home", "mkt_p_draw", "mkt_p_away"]].values
    mkt_ll = logloss_rows(mkt, y)
    rows = []
    for name, p in preds.items():
        pm = p.loc[mask, P1X2].values
        ll = logloss_rows(pm, y)
        d = ll - mkt_ll
        row = {"modelo": name, "n": int(mask.sum()), "logloss": ll.mean(), "rps": rps_rows(pm, y).mean(),
               "brier": brier_rows(pm, y).mean(), "vs_mercado": d.mean()}
        row["ic_lo"], row["ic_hi"] = boot_ci(d)
        if "p_over" in p:
            row["ou_logloss"] = binary_logloss_rows(p.loc[mask, "p_over"].values, df.over[mask].values).mean()
        rows.append(row)
    return pd.DataFrame(rows)


def breakdown(df: pd.DataFrame, preds: dict[str, pd.DataFrame], mask: pd.Series,
              groups: dict[str, np.ndarray], names: list[str]) -> pd.DataFrame:
    """vs mercado (con IC) y empate medio previsto frente al real, por subgrupo de partidos."""
    rows = []
    for group, g in groups.items():
        m = mask & g
        y = df.result[m].values
        mkt = df.loc[m, ["mkt_p_home", "mkt_p_draw", "mkt_p_away"]].values
        mkt_ll = logloss_rows(mkt, y)
        for name in names:
            d = logloss_rows(preds[name].loc[m, P1X2].values, y) - mkt_ll
            lo, hi = boot_ci(d)
            rows.append({"grupo": group, "modelo": name, "n": int(m.sum()), "vs_mercado": d.mean(),
                         "ic_lo": lo, "ic_hi": hi, "p_empate": preds[name].loc[m, "p_draw"].mean(),
                         "p_empate_mercado": mkt[:, 1].mean(), "empates": (y == 1).mean()})
    return pd.DataFrame(rows)


def betting(df: pd.DataFrame, p: pd.DataFrame, mask: pd.Series, edge: float = 0.03) -> dict:
    """Apuesta plana al resultado con mayor ventaja sobre el mercado pre-cierre si supera `edge`.

    CLV: probabilidad de cierre − probabilidad pre-cierre del resultado elegido (pp).
    ROI: con la cuota media pre-cierre (con margen).
    """
    labels = ["home", "draw", "away"]
    q = df.loc[mask, [f"mkt_p_{l}" for l in labels]].values
    c = df.loc[mask, [f"close_p_{l}" for l in labels]].values
    odds = df.loc[mask, [f"mkt_odds_{l}" for l in labels]].values
    pm = p.loc[mask, P1X2].values
    gap = pm - q
    pick = gap.argmax(1)
    sel = (gap.max(1) > edge) & ~np.isnan(c).any(1)
    i = np.arange(len(pick))[sel]
    clv = (c[i, pick[sel]] - q[i, pick[sel]]) * 100
    profit = np.where(df.result[mask].values[sel] == pick[sel], odds[i, pick[sel]] - 1, -1)
    return {"apuestas": int(sel.sum()), "clv_pp": float(clv.mean()), "clv_ic": boot_ci(clv),
            "roi": float(profit.mean()), "roi_ic": boot_ci(profit)}


def lineup_test(df, preds, mkt_x, has_mkt) -> tuple[pd.DataFrame, dict]:
    """Valor del once titular (conocido ~1 h antes): test en 2025/26, única temporada de test
    con datos de Transfermarkt. Se compara con el mercado pre-cierre y con el de cierre."""
    xi = lineups.features(df)
    dc = pd.DataFrame(logits(preds["Dixon-Coles xG/goles"][P1X2].values), columns=["d_h", "d_a"], index=df.index)
    sets = {"Dixon-Coles xG/goles": (dc, [2023, 2024, 2025]),
            "Dixon-Coles + once": (pd.concat([dc, xi[["xi_log_diff", "xi_rel_diff"]]], axis=1), [2023, 2024, 2025]),
            "Mercado + once": (pd.concat([mkt_x, xi[["xi_log_diff", "xi_rel_diff"]]], axis=1), [2025])}
    mask = has_mkt & (df.season == 2025) & xi.xi_rel_diff.notna()
    y = df.result[mask].values
    pre = logloss_rows(df.loc[mask, ["mkt_p_home", "mkt_p_draw", "mkt_p_away"]].values, y)
    close = logloss_rows(df.loc[mask, ["close_p_home", "close_p_draw", "close_p_away"]].values, y)
    rows = [{"modelo": "Mercado pre-cierre", "logloss": pre.mean()}, {"modelo": "Mercado cierre", "logloss": close.mean()}]
    for name, (X, seasons) in sets.items():
        p = expanding(df, X, logistic, seasons)
        ll = logloss_rows(p.loc[mask, P1X2].values, y)
        (lo, hi), (clo, chi) = boot_ci(ll - pre), boot_ci(ll - close)
        rows.append({"modelo": name, "logloss": ll.mean(), "vs_pre": (ll - pre).mean(), "vs_pre_lo": lo,
                     "vs_pre_hi": hi, "vs_cierre": (ll - close).mean(), "vs_cierre_lo": clo, "vs_cierre_hi": chi})
    move = (np.log(df.close_p_home / df.close_p_away) - np.log(df.mkt_p_home / df.mkt_p_away))
    m = has_mkt & xi.xi_rel_diff.notna()
    r = float(np.corrcoef(xi.xi_rel_diff[m], move[m])[0, 1])
    return pd.DataFrame(rows), {"n": int(m.sum()), "correlacion": r, "r2": r ** 2}


# ---------------------------------------------------------------- principal

def run() -> dict:
    df = data.load()
    pred_mask = df.season >= FIRST_PRED
    val, test = df.season.isin(VAL), df.season.isin(TEST)
    preds: dict[str, pd.DataFrame] = {}

    # Mercado como "modelo" (referencia)
    preds["Mercado pre-cierre"] = df[["mkt_p_home", "mkt_p_draw", "mkt_p_away", "mkt_p_over"]].set_axis(
        P1X2 + ["p_over"], axis=1)
    preds["Mercado cierre"] = df[["close_p_home", "close_p_draw", "close_p_away", "close_p_over"]].set_axis(
        P1X2 + ["p_over"], axis=1)
    freq = expanding(df, pd.DataFrame({"c": np.zeros(len(df))}, index=df.index),
                     lambda: LogisticRegression(max_iter=1000), VAL + TEST)
    preds["Frecuencias"] = freq

    # 1. Modelos de goles
    log.info("ajustando modelos de goles en validación…")
    tg = tune_goals(df)
    chosen, lams = {}, {}
    for name, cfg in (("Dixon-Coles goles", tg["best_goals_only"]), ("Dixon-Coles xG/goles", tg["best"]),
                      ("Dixon-Coles inflado", tg["best_inflated"])):
        key = (cfg["goal_weight"], cfg["half_life"], cfg["alpha"])
        if key not in lams:
            lams[key] = goals.lambdas(df, pred_mask, goal_weight=cfg["goal_weight"],
                                      half_life=cfg["half_life"], alpha=cfg["alpha"])
        preds[name] = goals.probs(lams[key], cfg["rho"], cfg["draw_inflation"]).reindex(df.index)
        chosen[name] = {k: cfg[k] for k in ("goal_weight", "half_life", "alpha", "rho", "draw_inflation")}
    best_g = tg["best"]
    lam_dc = lams[(best_g["goal_weight"], best_g["half_life"], best_g["alpha"])]

    # 2. Ratings
    log.info("ajustando ratings…")
    te, tp = tune_elo(df), tune_pi(df)
    elo_base = ratings.elo(df)  # el Elo actual de features.py
    best_e = te.iloc[0].to_dict()
    elo_best = ratings.elo(df, k=best_e["k"], home=best_e["home"], start_new=best_e["start_new"],
                           xg_weight=best_e["xg_weight"])
    best_p = tp.iloc[0].to_dict()
    pi_best = ratings.pi_ratings(df, lam=best_p["lam"], gamma=best_p["gamma"], xg_weight=best_p["xg_weight"])
    chosen["Elo ajustado"], chosen["Pi-ratings"] = best_e, best_p
    seasons = VAL + TEST
    preds["Elo actual"] = expanding(df, elo_base.to_frame("r"), logistic, seasons)
    preds["Elo ajustado"] = expanding(df, elo_best.to_frame("r"), logistic, seasons)
    preds["Pi-ratings"] = expanding(df, pi_best.to_frame("r"), logistic, seasons)

    # 2b. Ascendidos (valor de plantilla) y capa de empate
    log.info("ascendidos y capa de empate…")
    sv = squads.values(df)
    squad = {(lg, s, t): np.log(v) for lg, s, t, v in sv[["league", "season", "team", "squad_value"]].values
             if np.isfinite(v)}
    ts = tune_squad(df, best_e, squad)
    best_w = float(ts.iloc[0].value_weight)
    elo_squad = ratings.elo(df, k=best_e["k"], home=best_e["home"], start_new=best_e["start_new"],
                            xg_weight=best_e["xg_weight"], squad=squad, value_weight=best_w)
    preds["Elo + plantilla"] = expanding(df, elo_squad.to_frame("r"), logistic, seasons)
    td = tune_draw(df, draw_features(elo_best, lam_dc))
    draw_cols = DRAW_SETS[td.iloc[0].variables]
    chosen["Elo + plantilla"] = {"value_weight": best_w}
    chosen["Capa de empate"] = {"variables": td.iloc[0].variables}
    preds["Elo + capa de empate"] = expanding(df, draw_features(elo_best, lam_dc)[draw_cols], logistic, seasons)
    preds["Elo + plantilla + capa de empate"] = expanding(df, draw_features(elo_squad, lam_dc)[draw_cols],
                                                          logistic, seasons)

    # 3. Meta-modelos
    feats = pd.read_parquet(PROCESSED / "features.parquet").set_index("match_id")
    form_cols = ["diff_ewm_xg_for", "diff_ewm_xg_against", "diff_ewm_goals_for", "diff_ewm_goals_against",
                 "diff_ewm_points", "diff_rest_days", "home_rest_days", "away_rest_days"]
    form = feats.loc[df.match_id, form_cols].set_index(df.index)
    dc = preds["Dixon-Coles xG/goles"]
    base = pd.DataFrame(logits(dc[P1X2].values), columns=["dc_h", "dc_a"], index=df.index)
    base["elo"], base["pi"] = elo_best, pi_best
    meta = pd.concat([base, form], axis=1)
    seasons = [VAL[0] - 1] + VAL + TEST  # 2023/24 también, para poder apilar con el mercado
    preds["Meta logística"] = expanding(df, meta, logistic, seasons)
    preds["Meta árboles"] = expanding(
        df, meta, lambda: HistGradientBoostingClassifier(max_iter=200, learning_rate=0.03, max_depth=3,
                                                         l2_regularization=1.0, random_state=0), seasons)

    # 4. ¿Añade algo al mercado? Logística sobre log-odds del mercado + del modelo
    mkt_x = pd.DataFrame(logits(df[["mkt_p_home", "mkt_p_draw", "mkt_p_away"]].values),
                         columns=["m_h", "m_a"], index=df.index)
    preds["Mercado recalibrado"] = expanding(df, mkt_x, logistic, seasons)
    for name in ("Dixon-Coles xG/goles", "Meta logística"):
        x = pd.concat([mkt_x, pd.DataFrame(logits(preds[name][P1X2].values), columns=["x_h", "x_a"],
                                           index=df.index)], axis=1)
        preds[f"Mercado + {name}"] = expanding(df, x, logistic, seasons)

    has_mkt = df[["mkt_p_home", "close_p_home"]].notna().all(1)
    xi_table, xi_move = lineup_test(df, preds, mkt_x, has_mkt)
    tables = {"validación 2024/25": report(df, preds, val & has_mkt),
              "test 2025/26–2026/27": report(df, preds, test & has_mkt)}
    new = ratings._newcomers(df)
    promoted = np.array([(lg, s, h) in new or (lg, s, a) in new
                         for lg, s, h, a in zip(df.league, df.season, df.home, df.away)])
    close = df[["mkt_p_home", "mkt_p_draw", "mkt_p_away"]].max(1).values < 0.40
    groups = {"todos": np.ones(len(df), bool), "igualados (favorito < 40 %)": close,
              "con ascendido": promoted, "sin ascendido": ~promoted}
    focus = ["Dixon-Coles xG/goles", "Dixon-Coles inflado", "Elo ajustado", "Elo + plantilla",
             "Elo + capa de empate", "Elo + plantilla + capa de empate"]
    split = {k: breakdown(df, preds, m & has_mkt, groups, focus) for k, m in
             (("validación 2024/25", val), ("test 2025/26–2026/27", test))}
    vs_elo = {}  # mejora directa frente al modelo de partida (emparejada por partido), en test
    m = test & has_mkt
    for name, ref in (("Dixon-Coles inflado", "Dixon-Coles xG/goles"), ("Elo + plantilla", "Elo ajustado"),
                      ("Elo + capa de empate", "Elo ajustado"), ("Elo + plantilla + capa de empate", "Elo ajustado")):
        d = (logloss_rows(preds[name].loc[m, P1X2].values, df.result[m].values)
             - logloss_rows(preds[ref].loc[m, P1X2].values, df.result[m].values))
        vs_elo[f"{name} − {ref}"] = {"diferencia": float(d.mean()), "ic": boot_ci(d)}
    bets = {name: betting(df, preds[name], test & has_mkt) for name in
            ("Dixon-Coles xG/goles", "Meta logística", "Meta árboles", "Mercado + Dixon-Coles xG/goles")}

    out = df[["match_id", "league", "season", "result", "over"]].copy()
    for name, p in preds.items():
        for c in p.columns:
            out[f"{name}|{c}"] = p[c]
    out[pred_mask].to_parquet(PROCESSED / "model_predictions.parquet", index=False)
    result = {"elegidos": chosen, "tablas": {k: v.to_dict("records") for k, v in tables.items()},
              "apuestas_test": bets, "once_titular_2025": xi_table.to_dict("records"),
              "once_titular_movimiento": xi_move,
              "desglose": {k: v.to_dict("records") for k, v in split.items()},
              "mejora_frente_a_base_test": vs_elo,
              "busqueda_plantilla": ts.to_dict("records"), "busqueda_capa_empate": td.to_dict("records"),
              "valor_plantilla_ascendidos": sv.assign(squad_value=sv.squad_value / 1e6)
              .loc[lambda d: [(lg, s, t) in new for lg, s, t in zip(d.league, d.season, d.team)]]
              .to_dict("records"),
              "busqueda_goles": tg["table"].sort_values("ll").head(10).to_dict("records"),
              "busqueda_elo": te.head(10).to_dict("records"), "busqueda_pi": tp.head(10).to_dict("records")}
    (PROCESSED / "model_report.json").write_text(json.dumps(result, indent=1, default=float))
    return {"tables": tables, "split": split, "vs_base": vs_elo, "ts": ts, "td": td, "bets": bets, "xi": xi_table, "xi_move": xi_move, "chosen": chosen, "tg": tg, "te": te, "tp": tp}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    pd.set_option("display.width", 200)
    r = run()
    print("Elegidos en validación:", json.dumps(r["chosen"], indent=1, default=float))
    for name, t in r["tables"].items():
        print(f"\n== {name}")
        print(t.round(4).to_string(index=False))
    for name, t in r["split"].items():
        print(f"\n== Desglose {name}")
        print(t.round(4).to_string(index=False))
    print("\n== Frente a su modelo base (test):", json.dumps(r["vs_base"], default=lambda x: round(float(x), 4)))
    print("\n== Once titular (Transfermarkt), test 2025/26")
    print(r["xi"].round(4).to_string(index=False))
    print("Movimiento de cuota pre-cierre -> cierre explicado por el once:", r["xi_move"])
    print("\n== Apuestas simuladas en test (ventaja > 3 pp sobre pre-cierre)")
    for name, b in r["bets"].items():
        print(name, json.dumps(b, default=lambda x: round(float(x), 4)))
