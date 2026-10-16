"""Variables pre-partido: para cada partido, solo información disponible ANTES de su inicio.

Por cada equipo (local y visitante):
  - Forma: media de los últimos 5 y 10 partidos (r5_, r10_) y media exponencial (ewm_, semivida
    de 5 partidos) de lo que genera (<stat>_for) y lo que concede (<stat>_against).
    Los partidos se ordenan por hora de inicio y se desplazan una posición (shift), así que el
    partido que se predice nunca entra en su propia media. La forma cruza temporadas.
  - elo: rating Elo antes del partido (K=20, ventaja local 60 puntos, 1500 al aparecer).
  - rest_days: días desde su partido anterior en estos datos (solo liga: no se ven las copas).
  - n_prev: partidos previos del equipo en los datos (forma poco fiable si es bajo).
Mercado (Football-Data):
  - mkt_p_home/draw/away: cuotas medias PRE-CIERRE sin margen (método de potencia,
    futdata.models.margin). mkt_odds_* son esas cuotas tal cual y mkt_overround su margen. Se capturan el
    viernes o el martes antes del partido: válidas para predecir a 1-3 días vista.
  - close_p_*: cuotas medias de CIERRE sin margen. Solo como referencia: no son información
    disponible días antes del partido.
Objetivo: result (H/D/A), home_goals, away_goals.

Salida: data/processed/features.parquet (un partido por fila)
Uso:    python -m futdata.features
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from futdata.common import RAW, fd_code, log
from futdata.matches import PROCESSED
from futdata.models.margin import fair

STATS = {  # nombre de la variable -> columna de team_match_stats
    "goals": "goals", "xg": "pa_expected_goals", "npxg": "pa_expected_goals_non_penalty",
    "xgot": "pa_expected_goals_on_target", "shots": "pa_total_shots",
    "sot": "pa_shots_on_target", "big_chances": "pa_big_chance", "box_touches": "pa_touches_opp_box",
    "corners": "pa_corners", "pass_acc": "pa_accurate_passes_pct",
}
OWN_ONLY = {"possession": "pa_possession", "points": "points"}  # sin versión "against"
WINDOWS = (5, 10)
EWM_HALFLIFE = 5
ELO_K, ELO_HOME, ELO_START = 20.0, 60.0, 1500.0


def _team_rows() -> pd.DataFrame:
    """Una fila por equipo y partido con sus estadísticas y las del rival (= concedidas)."""
    stats = pd.read_parquet(PROCESSED / "team_match_stats.parquet")
    stats["kickoff"] = stats["kickoff_utc"].fillna(
        stats["date"].dt.tz_localize("UTC") + pd.Timedelta(hours=15))
    stats["points"] = np.select([stats.goals > stats.goals_against, stats.goals == stats.goals_against],
                                [3, 1], 0)
    cols = list(STATS.values())
    opp = stats[["match_id", "side"] + cols].copy()
    opp["side"] = opp["side"].map({"home": "away", "away": "home"})
    opp = opp.rename(columns={c: f"{c}__opp" for c in cols})
    rows = stats.merge(opp, on=["match_id", "side"], how="left")
    out = rows[["match_id", "league", "season", "date", "kickoff", "side", "team", "opponent"]].copy()
    for name, col in STATS.items():
        out[f"{name}_for"] = rows[col]
        out[f"{name}_against"] = rows[f"{col}__opp"]
    for name, col in OWN_ONLY.items():
        out[name] = rows[col]
    return out.sort_values(["kickoff", "match_id", "side"]).reset_index(drop=True)


def form_features(rows: pd.DataFrame) -> pd.DataFrame:
    """Medias de partidos ANTERIORES de cada equipo (shift(1) antes de cualquier ventana)."""
    values = [c for c in rows.columns if c.endswith(("_for", "_against"))] + list(OWN_ONLY)
    rows = rows.sort_values(["team", "kickoff"])
    prev = rows.groupby("team")[values].shift(1)
    prev["team"] = rows["team"]
    group = prev.groupby("team")[values]
    out = rows[["match_id", "side", "team", "kickoff"]].copy()
    for w in WINDOWS:
        rolled = group.rolling(w, min_periods=1).mean().reset_index(level=0, drop=True)
        out = out.join(rolled[values].add_prefix(f"r{w}_"))  # alineado por índice
    ewm = group.transform(lambda s: s.ewm(halflife=EWM_HALFLIFE, ignore_na=True).mean())
    out = out.join(ewm[values].add_prefix("ewm_"))
    out["n_prev"] = rows.groupby("team").cumcount()
    last = rows.groupby("team")["kickoff"].shift(1)
    out["rest_days"] = (rows["kickoff"] - last).dt.total_seconds() / 86400
    return out


def elo_ratings(matches: pd.DataFrame) -> pd.DataFrame:
    """Elo antes de cada partido, recorriendo los partidos en orden cronológico."""
    ratings: dict[str, float] = {}
    out = []
    for m in matches.sort_values(["kickoff", "match_id"]).itertuples():
        rh, ra = ratings.get(m.home, ELO_START), ratings.get(m.away, ELO_START)
        out.append((m.match_id, rh, ra))
        expected = 1 / (1 + 10 ** ((ra - rh - ELO_HOME) / 400))
        score = 1.0 if m.home_goals > m.away_goals else 0.5 if m.home_goals == m.away_goals else 0.0
        margin = np.log1p(abs(m.home_goals - m.away_goals)) + 1  # más peso a goleadas
        delta = ELO_K * margin * (score - expected)
        ratings[m.home], ratings[m.away] = rh + delta, ra - delta
    return pd.DataFrame(out, columns=["match_id", "home_elo", "away_elo"])


def market(matches: pd.DataFrame) -> pd.DataFrame:
    """Probabilidades sin margen (método de potencia) de las cuotas medias pre-cierre y de cierre,
    más las cuotas medias pre-cierre tal cual y su margen."""
    rows = []
    for (league, season), group in matches.groupby(["league", "season"]):
        csv = pd.read_csv(RAW / "football_data" / fd_code(season) / f"{league}.csv",
                          encoding="latin-1", on_bad_lines="skip")
        for m in group.itertuples():
            src = csv.loc[m.fd_row]
            row = {"match_id": m.match_id}
            for prefix, cols in (("mkt", ("AvgH", "AvgD", "AvgA")), ("close", ("AvgCH", "AvgCD", "AvgCA"))):
                odds = pd.to_numeric(pd.Series([src.get(c) for c in cols]), errors="coerce").to_numpy(float)
                probs = fair(odds[None, :])[0]
                for label, o, p in zip(("home", "draw", "away"), odds, probs):
                    row[f"{prefix}_p_{label}"] = p
                    if prefix == "mkt":
                        row[f"mkt_odds_{label}"] = o if o > 1 else np.nan
                if prefix == "mkt":
                    row["mkt_overround"] = (1 / odds).sum() - 1 if (odds > 1).all() else np.nan
            rows.append(row)
    return pd.DataFrame(rows)


def build() -> pd.DataFrame:
    matches = pd.read_parquet(PROCESSED / "matches.parquet")
    matches["kickoff"] = matches["kickoff_utc"].fillna(
        matches["date"].dt.tz_localize("UTC") + pd.Timedelta(hours=15))
    form = form_features(_team_rows())
    feature_cols = [c for c in form.columns if c not in ("match_id", "side", "team", "kickoff")]
    home = form[form.side == "home"].set_index("match_id")[feature_cols].add_prefix("home_")
    away = form[form.side == "away"].set_index("match_id")[feature_cols].add_prefix("away_")

    out = matches[["match_id", "league", "season", "date", "kickoff", "home", "away",
                   "home_goals", "away_goals"]].copy()
    out["result"] = np.select([out.home_goals > out.away_goals, out.home_goals == out.away_goals],
                              ["H", "D"], "A")
    out = (out.merge(elo_ratings(matches), on="match_id")
              .join(home, on="match_id").join(away, on="match_id")
              .merge(market(matches), on="match_id", how="left"))
    out["elo_diff"] = out.home_elo - out.away_elo
    for c in feature_cols:
        if c.startswith(("r5_", "r10_", "ewm_")) or c == "rest_days":
            out[f"diff_{c}"] = out[f"home_{c}"] - out[f"away_{c}"]
    out = out.sort_values(["kickoff", "match_id"]).reset_index(drop=True)
    out.to_parquet(PROCESSED / "features.parquet", index=False)
    log.info("features: %d partidos, %d columnas", *out.shape)
    return out


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    df = build()
    print(f"{len(df)} partidos x {df.shape[1]} columnas")
    print("resultados:", df.result.value_counts(normalize=True).round(3).to_dict())
    print("con cuotas pre-cierre:", f"{df.mkt_p_home.notna().mean():.1%}")
