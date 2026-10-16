"""Funciones puras que alimentan la API web. Solo leen data/processed y data/raw; no escriben nada.

Cada función devuelve estructuras JSON-serializables: sin NaN (se sustituyen por None), floats
redondeados a 3 decimales y fechas en ISO 8601 UTC. Si el recurso no existe, devuelve None.

Fuentes:
  data/processed/matches.parquet            partidos (marcador, ids de fuente)
  data/processed/team_match_stats.parquet   estadísticas por equipo y partido (pa_*, adv_*)
  data/processed/features.parquet           variables pre-partido (Elo, forma, mercado)
  data/processed/team_names.csv             nombres ESPN -> canónicos
  data/raw/pitchapi/match/<LIGA>/<TEMP>/<id>/   tiros, eventos, alineaciones, mapas de calor
  data/raw/espn/scoreboard/<LIGA>/<YYYYMM>.json  calendario (próximos partidos)
  data/raw/football_data/fixtures.csv       próximos partidos con cuotas (puede faltar)
"""
from __future__ import annotations

import functools
import json
import math
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from futdata.common import LEAGUES, RAW, utcnow
from futdata.matches import PROCESSED
from futdata.models.margin import fair

PITCHAPI = RAW / "pitchapi" / "match"
ESPN_SCOREBOARD = RAW / "espn" / "scoreboard"
FIXTURES = RAW / "football_data" / "fixtures.csv"
TEAM_NAMES = PROCESSED / "team_names.csv"

XPTS_MAX_GOALS = 10
LAST_FORM = 5

# Estadísticas de la ficha del partido: (clave, etiqueta, grupo, columna de team_match_stats)
STAT_SPEC = [
    ("xg", "xG", "Ataque", "pa_expected_goals"),
    ("npxg", "xG sin penaltis", "Ataque", "pa_expected_goals_non_penalty"),
    ("xgot", "xG a puerta", "Ataque", "pa_expected_goals_on_target"),
    ("shots", "Tiros", "Ataque", "pa_total_shots"),
    ("shots_on_target", "Tiros a puerta", "Ataque", "pa_shots_on_target"),
    ("big_chances", "Grandes ocasiones", "Ataque", "pa_big_chance"),
    ("box_touches", "Toques en el área rival", "Ataque", "pa_touches_opp_box"),
    ("corners", "Córners", "Ataque", "pa_corners"),
    ("dribbles", "Regates", "Ataque", "pa_dribbles_succeeded"),
    ("possession", "Posesión", "Posesión", "pa_possession"),
    ("passes", "Pases", "Posesión", "pa_passes"),
    ("pass_acc", "Precisión de pase %", "Posesión", "pa_accurate_passes_pct"),
    ("duels_won", "Duelos ganados", "Defensa", "pa_duel_won"),
    ("tackles", "Entradas", "Defensa", "pa_tackles"),
    ("interceptions", "Intercepciones", "Defensa", "pa_interceptions"),
    ("clearances", "Despejes", "Defensa", "pa_clearances"),
    ("saves", "Paradas", "Defensa", "pa_keeper_saves"),
    ("fouls", "Faltas", "Disciplina", "pa_fouls"),
    ("yellow", "Amarillas", "Disciplina", "pa_yellow_cards"),
    ("red", "Rojas", "Disciplina", "pa_red_cards"),
    ("offsides", "Fueras de juego", "Disciplina", "pa_offsides"),
]

# Estadísticas avanzadas de la ficha: clave -> columna adv_ de team_match_stats
ADV_SPEC = {
    "xt": "adv_xt_total",
    "vaep": "adv_vaep_total",
    "ppda": "adv_ppda",
    "field_tilt": "adv_field_tilt",
    "progressive_passes": "adv_progressive_passes",
    "progressive_carries": "adv_progressive_carries",
    "box_entries": "adv_box_entries",
    "high_turnovers": "adv_high_turnovers",
}

SHOT_OUTCOME = {"Goal": "goal", "AttemptSaved": "saved", "Miss": "miss", "Post": "post",
                "Blocked": "blocked"}
SHOT_BODY = {"RightFoot": "right_foot", "LeftFoot": "left_foot", "Header": "head"}


# ---------------------------------------------------------------- utilidades

def _iso(value) -> str | None:
    """Timestamp -> ISO 8601 UTC (con +00:00). None/NaT -> None."""
    if value is None or pd.isna(value):
        return None
    ts = pd.Timestamp(value)
    ts = ts.tz_localize("UTC") if ts.tzinfo is None else ts.tz_convert("UTC")
    return ts.isoformat(timespec="seconds")


def _clean(value):
    """Convierte recursivamente a tipos JSON: NaN -> None, floats a 3 decimales, numpy -> Python."""
    if isinstance(value, dict):
        return {str(k): _clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_clean(v) for v in value]
    if value is None or value is pd.NaT or value is pd.NA:
        return None
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if isinstance(value, (int, np.integer)):
        return int(value)
    if isinstance(value, (float, np.floating)):
        f = float(value)
        return None if (math.isnan(f) or math.isinf(f)) else round(f, 3)
    if isinstance(value, pd.Timestamp):
        return _iso(value)
    return value


def _public(func):
    """Decorador: aplica _clean a la salida de cada función pública."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        return _clean(func(*args, **kwargs))
    return wrapper


def _read_json(path: Path):
    """Devuelve el bloque 'data' de un fichero JSON de PitchAPI, o None si no existe."""
    if not path.is_file():
        return None
    return json.loads(path.read_bytes()).get("data")


def _pitch_dir(league: str, season: int, pitchapi_id) -> Path | None:
    if not isinstance(pitchapi_id, str) or not pitchapi_id:
        return None
    return PITCHAPI / league / str(int(season)) / pitchapi_id


def _letter(gf: int, ga: int) -> str:
    return "W" if gf > ga else "D" if gf == ga else "L"


def _poisson_wdl(lam_home: float, lam_away: float) -> tuple[float, float, float]:
    """P(gana local), P(empate), P(gana visitante) con goles Poisson independientes (0..10)."""
    def dist(lam):
        return [math.exp(-lam) * lam ** k / math.factorial(k) for k in range(XPTS_MAX_GOALS + 1)]
    ph, pa = dist(lam_home), dist(lam_away)
    win = draw = loss = 0.0
    for i, p_i in enumerate(ph):
        for j, p_j in enumerate(pa):
            p = p_i * p_j
            if i > j:
                win += p
            elif i == j:
                draw += p
            else:
                loss += p
    return win, draw, loss


def _nn(value):
    """Valor numérico o None si falta."""
    if value is None or pd.isna(value):
        return None
    return float(value)


# ---------------------------------------------------------------- carga (cacheada)

@functools.lru_cache(maxsize=None)
def _stats_frame() -> pd.DataFrame:
    """team_match_stats restringido a las columnas que usa la API."""
    cols = ["match_id", "side", "team", "opponent", "goals", "goals_against",
            "pa_expected_goals", "pa_expected_goals_non_penalty", "pa_expected_goals_on_target",
            "pa_total_shots", "pa_shots_on_target", "pa_big_chance", "pa_touches_opp_box",
            "pa_corners", "pa_dribbles_succeeded", "pa_possession", "pa_passes",
            "pa_accurate_passes_pct", "pa_duel_won", "pa_tackles", "pa_interceptions",
            "pa_clearances", "pa_keeper_saves", "pa_fouls", "pa_yellow_cards", "pa_red_cards",
            "pa_offsides"] + list(ADV_SPEC.values())
    return pd.read_parquet(PROCESSED / "team_match_stats.parquet", columns=cols)


@functools.lru_cache(maxsize=None)
def _stats_by_key() -> dict:
    """(match_id, side) -> dict de estadísticas."""
    return _stats_frame().set_index(["match_id", "side"]).to_dict("index")


@functools.lru_cache(maxsize=None)
def _feature_frame() -> pd.DataFrame:
    """features.parquet restringido a las variables pre-partido que usa la API."""
    cols = ["match_id", "league", "season", "home", "away",
            "mkt_p_home", "mkt_p_draw", "mkt_p_away", "mkt_overround", "mkt_odds_home", "mkt_odds_draw", "mkt_odds_away", "close_p_home", "close_p_draw", "close_p_away",
            "elo_diff", "home_elo", "away_elo", "home_rest_days", "away_rest_days"]
    for side in ("home", "away"):
        for name in ("r5_goals_for", "r5_goals_against", "r5_xg_for", "r5_xg_against",
                     "r5_points", "ewm_xg_for", "ewm_xg_against"):
            cols.append(f"{side}_{name}")
    return pd.read_parquet(PROCESSED / "features.parquet", columns=cols)


@functools.lru_cache(maxsize=None)
def _feature_by_id() -> dict:
    return _feature_frame().set_index("match_id").to_dict("index")


# Modelo propio que se enseña en la web: el mejor sin cuotas en el test 2025/26–2026/27.
SHOWN_MODEL = "Elo ajustado"


@functools.lru_cache(maxsize=None)
def _model_by_id() -> dict:
    """match_id -> probabilidades fuera de muestra de SHOWN_MODEL (model_predictions.parquet)."""
    path = PROCESSED / "model_predictions.parquet"
    if not path.is_file():
        return {}
    cols = [f"{SHOWN_MODEL}|p_{k}" for k in ("home", "draw", "away")]
    df = pd.read_parquet(path, columns=["match_id", *cols]).dropna()
    return {r[0]: {"home": r[1], "draw": r[2], "away": r[3]} for r in df.itertuples(index=False)}


def _season_of(kickoff: pd.Timestamp) -> int:
    """Temporada (año de inicio) de un partido: de julio a junio."""
    return kickoff.year if kickoff.month >= 7 else kickoff.year - 1


def elo_state(history: pd.DataFrame, params: dict) -> dict:
    """Estado de SHOWN_MODEL tras el último partido de `history` (tabla de futdata.models.data.load).

    Mismo procedimiento que la evaluación: Elo con los parámetros elegidos en validación y capa
    logística sobre la diferencia de Elo, entrenada con las temporadas anteriores a la del partido.
    """
    from futdata.models import ratings
    diff, final = ratings.elo_pass(history, k=params["k"], home=params["home"],
                                   start_new=params["start_new"], xg_weight=params["xg_weight"])
    return {"history": history, "diff": diff.to_frame("r"), "ratings": final, "home_adv": params["home"],
            "last_kickoff": history.kickoff.max(), "layers": {}}


def elo_forecast(state: dict, home: str, away: str, kickoff: pd.Timestamp) -> dict | None:
    """Probabilidades 1X2 de un partido futuro. None si algún equipo no tiene historial o si el
    estado incluye partidos jugados a la vez o después del saque inicial (no sería fuera de muestra)."""
    from futdata.models import evaluate
    if home not in state["ratings"] or away not in state["ratings"] or kickoff <= state["last_kickoff"]:
        return None
    season = _season_of(kickoff)
    if season not in state["layers"]:
        h = state["history"]
        train = (h.season >= evaluate.FIRST_PRED) & (h.season < season)
        state["layers"][season] = (evaluate.logistic().fit(state["diff"][train], h.result[train])
                                   if train.any() else None)
    layer = state["layers"][season]
    if layer is None:
        return None
    r = state["ratings"][home] - state["ratings"][away] + state["home_adv"]
    p = layer.predict_proba(pd.DataFrame({"r": [r]}))[0]
    return dict(zip(("home", "draw", "away"), (float(x) for x in p)))


@functools.lru_cache(maxsize=1)
def _upcoming_state() -> dict | None:
    """elo_state con todos los partidos jugados y los parámetros de model_report.json."""
    report = PROCESSED / "model_report.json"
    if not report.is_file():
        return None
    params = json.loads(report.read_bytes()).get("elegidos", {}).get(SHOWN_MODEL)
    if not params:
        return None
    from futdata.models import data
    return elo_state(data.load(), params)


@functools.lru_cache(maxsize=None)
def _base() -> pd.DataFrame:
    """Un partido por fila con todo lo necesario para listados: marcador, xG, mercado, ficha."""
    m = pd.read_parquet(PROCESSED / "matches.parquet")
    m["sort_ts"] = m["kickoff_utc"].fillna(m["date"].dt.tz_localize("UTC") + pd.Timedelta(hours=15))
    m = m.sort_values(["sort_ts", "match_id"]).reset_index(drop=True)

    st = _stats_frame()
    xg = st.pivot(index="match_id", columns="side", values="pa_expected_goals")
    m["home_xg"] = m["match_id"].map(xg["home"])
    m["away_xg"] = m["match_id"].map(xg["away"])

    feat = _feature_frame().set_index("match_id")
    m["mkt_home"] = m["match_id"].map(feat["mkt_p_home"])
    m["mkt_draw"] = m["match_id"].map(feat["mkt_p_draw"])
    m["mkt_away"] = m["match_id"].map(feat["mkt_p_away"])

    m["kickoff"] = [_iso(v) for v in m["kickoff_utc"]]
    folders = [_pitch_dir(lg, s, pid) for lg, s, pid in zip(m.league, m.season, m.pitchapi_id)]
    m["pitch_dir"] = [str(d) if d is not None else None for d in folders]
    m["has_heatmaps"] = [d is not None and (d / "heatmaps.json").is_file() for d in folders]
    return m


@functools.lru_cache(maxsize=None)
def _base_by_id() -> dict:
    return _base().set_index("match_id", drop=False).to_dict("index")


@functools.lru_cache(maxsize=None)
def _timelines() -> tuple[dict, dict]:
    """Por equipo, lista cronológica de (match_id, W/D/L) y posición de cada partido en ella."""
    timeline: dict[str, list] = defaultdict(list)
    position: dict[tuple, int] = {}
    for r in _base().itertuples(index=False):
        for team, gf, ga in ((r.home, r.home_goals, r.away_goals), (r.away, r.away_goals, r.home_goals)):
            position[(team, r.match_id)] = len(timeline[team])
            timeline[team].append((r.match_id, _letter(int(gf), int(ga))))
    return dict(timeline), position


def _last_results(team: str, match_id: str) -> list[str]:
    """W/D/L de los hasta 5 partidos anteriores del equipo (el más reciente al final)."""
    timeline, position = _timelines()
    idx = position[(team, match_id)]
    return [letter for _, letter in timeline[team][max(0, idx - LAST_FORM):idx]]


@functools.lru_cache(maxsize=None)
def _espn_names() -> dict:
    """(liga, nombre ESPN) -> nombre canónico, solo traducciones aceptadas."""
    names = pd.read_csv(TEAM_NAMES)
    names = names[(names.source == "espn") & (names.accepted == True)]  # noqa: E712
    return {(r.league, r.name): r.canonical for r in names.itertuples(index=False)}


def _fixture_markets() -> dict:
    """(liga, fecha local UK, local, visitante) -> probabilidades sin margen de fixtures.csv."""
    if not FIXTURES.is_file():
        return {}
    df = pd.read_csv(FIXTURES, encoding="utf-8-sig")
    out = {}
    for r in df.to_dict("records"):
        if r.get("Div") not in LEAGUES:
            continue
        date = pd.to_datetime(r["Date"], format="%d/%m/%Y").date()
        key = (r["Div"], date, str(r["HomeTeam"]).strip(), str(r["AwayTeam"]).strip())
        odds = [r.get("AvgH"), r.get("AvgD"), r.get("AvgA")]
        if any(o is None or pd.isna(o) or float(o) <= 1 for o in odds):
            out[key] = None
            continue
        p = fair(np.array([odds], dtype=float))[0]
        out[key] = {"home": p[0], "draw": p[1], "away": p[2]}
    return out


# ---------------------------------------------------------------- consultas públicas

@functools.lru_cache(maxsize=1)
def _team_identity() -> dict:
    """Nombre completo (el de PitchAPI) y escudo de cada equipo, por nombre canónico."""
    names = pd.read_csv(PROCESSED / "team_names.csv")
    names = names[(names.source == "pitchapi") & names.accepted]
    canonical = {(r.league, r.name): r.canonical for r in names.itertuples(index=False)}
    out: dict = {}
    for path in sorted((RAW / "pitchapi" / "matches").glob("*/*.json")):  # las más recientes, al final
        data = json.loads(path.read_bytes())["data"]
        for m in data.get("matches", data) if isinstance(data, dict) else data:
            for side in ("home_team", "away_team"):
                team = m[side]
                key = canonical.get((path.parent.name, team["name"]))
                if key:
                    out[key] = {"name": team["name"], "crest": team.get("image_url")}
    colors_path = PROCESSED / "team_colors.json"  # generado por futdata.crests
    if colors_path.is_file():
        colors = json.loads(colors_path.read_bytes())
        for key, info in out.items():
            c = colors.get(key)
            info["color"] = c.get("color") if c else None
            if c:
                info["crest_remote"] = info["crest"]
                info["crest"] = f"/api/crests/{c['file']}"
    return out


@_public
def meta() -> dict:
    b = _base()
    st = _stats_frame()
    leagues = []
    for code, info in LEAGUES.items():
        seasons = sorted(int(s) for s in b.loc[b.league == code, "season"].unique())
        leagues.append({"code": code, "name": info["name"], "seasons": seasons})
    return {
        "generated_at": utcnow(),
        "data_through": b["date"].max().date().isoformat(),
        "counts": {
            "matches": len(b),
            "teams": len(set(b.home) | set(b.away)),
            "shots": int(st["pa_total_shots"].fillna(0).sum()),
        },
        "leagues": leagues,
        "teams": _team_identity(),
    }


@_public
def teams() -> list:
    b = _base()
    rows = pd.concat([
        b[["league", "season", "home"]].rename(columns={"home": "team"}),
        b[["league", "season", "away"]].rename(columns={"away": "team"}),
    ])
    out = []
    for (league, team), group in rows.groupby(["league", "team"]):
        out.append({"league": league, "team": team,
                    "seasons": sorted(int(s) for s in group["season"].unique())})
    return sorted(out, key=lambda t: (t["league"], t["team"]))


@_public
def table(league: str, season: int | None = None) -> dict | None:
    """Clasificación de una temporada con xG y xPts. Por defecto, la temporada más reciente."""
    if league not in LEAGUES:
        return None
    b = _base()
    lg = b[b.league == league]
    if lg.empty:
        return None
    season = int(lg.season.max()) if season is None else int(season)
    sub = lg[lg.season == season]
    if sub.empty:
        return None

    acc: dict[str, dict] = {}

    def slot(team: str) -> dict:
        return acc.setdefault(team, {"played": 0, "won": 0, "drawn": 0, "lost": 0, "gf": 0, "ga": 0,
                                     "pts": 0, "xg_for": 0.0, "xg_against": 0.0, "xg_n": 0,
                                     "xpts": 0.0, "form": []})

    for r in sub.itertuples(index=False):
        hg, ag = int(r.home_goals), int(r.away_goals)
        xh, xa = _nn(r.home_xg), _nn(r.away_xg)
        if xh is not None and xa is not None:
            p_win, p_draw, p_loss = _poisson_wdl(xh, xa)
            xpts_h, xpts_a = 3 * p_win + p_draw, 3 * p_loss + p_draw
        else:  # sin xG en alguno de los dos: se usan los puntos reales de ese partido
            xpts_h, xpts_a = (3, 0) if hg > ag else (1, 1) if hg == ag else (0, 3)
        for team, gf, ga, xg, xg_opp, xpts in (
            (r.home, hg, ag, xh, xa, xpts_h),
            (r.away, ag, hg, xa, xh, xpts_a),
        ):
            s = slot(team)
            s["played"] += 1
            s["gf"] += gf
            s["ga"] += ga
            letter = _letter(gf, ga)
            s[{"W": "won", "D": "drawn", "L": "lost"}[letter]] += 1
            s["pts"] += {"W": 3, "D": 1, "L": 0}[letter]
            s["xpts"] += xpts
            s["form"].append(letter)
            if xg is not None:
                s["xg_for"] += xg
                s["xg_n"] += 1
            if xg_opp is not None:
                s["xg_against"] += xg_opp

    ordered = sorted(acc.items(), key=lambda kv: (-kv[1]["pts"], -(kv[1]["gf"] - kv[1]["ga"]),
                                                  -kv[1]["gf"], kv[0]))
    rows = []
    for pos, (team, s) in enumerate(ordered, start=1):
        has_xg = s["xg_n"] > 0
        xg_for = s["xg_for"] if has_xg else None
        xg_against = s["xg_against"] if has_xg else None
        rows.append({
            "pos": pos, "team": team, "played": s["played"], "won": s["won"], "drawn": s["drawn"],
            "lost": s["lost"], "gf": s["gf"], "ga": s["ga"], "gd": s["gf"] - s["ga"], "pts": s["pts"],
            "xg_for": xg_for, "xg_against": xg_against,
            "xg_diff": (xg_for - xg_against) if has_xg else None,
            "xpts": s["xpts"], "form": s["form"][-LAST_FORM:],
        })
    return {"league": league, "season": season, "rows": rows}


def _match_item(rec: dict) -> dict:
    return {
        "match_id": rec["match_id"],
        "league": rec["league"],
        "season": int(rec["season"]),
        "kickoff": rec["kickoff"],
        "home": rec["home"],
        "away": rec["away"],
        "home_goals": int(rec["home_goals"]),
        "away_goals": int(rec["away_goals"]),
        "home_xg": rec["home_xg"],
        "away_xg": rec["away_xg"],
        "market": {"home": rec["mkt_home"], "draw": rec["mkt_draw"], "away": rec["mkt_away"]},
        "has_heatmaps": bool(rec["has_heatmaps"]),
    }


@_public
def matches(league: str | None = None, season: int | None = None, team: str | None = None,
            limit: int | None = None) -> list:
    """Partidos ordenados por hora de inicio, del más reciente al más antiguo."""
    b = _base()
    if league is not None:
        b = b[b.league == league]
    if season is not None:
        b = b[b.season == int(season)]
    if team is not None:
        b = b[(b.home == team) | (b.away == team)]
    b = b.sort_values(["sort_ts", "match_id"], ascending=[False, False])
    if limit:
        b = b.head(int(limit))
    return [_match_item(rec) for rec in b.to_dict("records")]


def _pre_match(side: str, team: str, match_id: str, feat: dict) -> dict:
    return {
        "elo": feat.get(f"{side}_elo"),
        "rest_days": feat.get(f"{side}_rest_days"),
        "form": {
            "xg_for": feat.get(f"{side}_r5_xg_for"),
            "xg_against": feat.get(f"{side}_r5_xg_against"),
            "goals_for": feat.get(f"{side}_r5_goals_for"),
            "goals_against": feat.get(f"{side}_r5_goals_against"),
            "points": feat.get(f"{side}_r5_points"),
        },
        "last5": _last_results(team, match_id),
    }


def _read_shots(folder: Path, home_id: str | None) -> list:
    data = _read_json(folder / "shots.json") or {}
    out = []
    for period in data.get("periods") or []:
        for s in period.get("shots") or []:
            player = s.get("player") or {}
            out.append({
                "side": "home" if s.get("team_id") == home_id else "away",
                "player": player.get("name"),
                "minute": s.get("minute"),
                "x": s.get("x"),
                "y": s.get("y"),
                "xg": s.get("expected_goals"),
                "xgot": s.get("expected_goals_on_target"),
                "outcome": SHOT_OUTCOME.get(s.get("event_type"), "other"),
                "situation": s.get("situation"),
                "body": SHOT_BODY.get(s.get("shot_type"), "other"),
            })
    return out


def _read_events(folder: Path, home_id: str | None) -> list:
    data = _read_json(folder / "events.json") or {}
    out = []
    for e in data.get("events") or []:
        is_sub = e.get("event_type") == "substitution"
        # En una sustitución, "player" es el que sale y "sub_in_player" el que entra.
        # Se muestra al que entra como jugador del evento y al que sale en "detail".
        main = (e.get("sub_in_player") if is_sub else e.get("player")) or {}
        out.append({
            "type": e.get("event_type"),
            "minute": e.get("minute"),
            "added": e.get("minute_added"),
            "side": "home" if e.get("team_id") == home_id else "away",
            "player": main.get("name"),
            "detail": ((e.get("player") or {}).get("name") if is_sub else None),
            "own_goal": bool(e.get("is_own_goal")),
            "penalty": bool(e.get("is_penalty")),
        })
    return out


def _read_momentum(folder: Path) -> list:
    data = _read_json(folder / "momentum.json") or {}
    return [{"minute": p.get("minute"), "value": p.get("value")} for p in data.get("points") or []]


def _read_lineups(folder: Path) -> dict | None:
    data = _read_json(folder / "lineups.json")
    if data is None:
        return None
    out = {}
    for side in ("home", "away"):
        t = data.get(side) or {}
        starters = []
        for p in t.get("starters") or []:
            shirt = p.get("shirt_number")
            starters.append({
                "name": p.get("name"),
                "number": int(shirt) if str(shirt).isdigit() else None,
                "x": p.get("pitch_x"),
                "y": p.get("pitch_y"),
                "captain": bool(p.get("is_captain")),
            })
        out[side] = {"formation": t.get("formation"),
                     "coach": (t.get("coach") or {}).get("name"),
                     "starters": starters}
    return out


def _read_heatmaps(folder: Path, home_id: str | None) -> dict | None:
    data = _read_json(folder / "heatmaps.json")
    if data is None:
        return None

    def side_of(entity: dict) -> str:
        return "home" if (entity.get("team") or {}).get("id") == home_id else "away"

    teams_out = {"home": [], "away": []}
    for t in data.get("teams") or []:
        teams_out[side_of(t)] = t.get("cells") or []
    players = sorted(data.get("players") or [], key=lambda p: p.get("actions") or 0, reverse=True)[:22]
    return {
        "grid": {"length": (data.get("grid") or {}).get("length"),
                 "width": (data.get("grid") or {}).get("width")},
        "teams": teams_out,
        "players": [{
            "name": (p.get("player") or {}).get("name"),
            "number": (p.get("player") or {}).get("shirt_number"),
            "side": side_of(p),
            "actions": p.get("actions"),
            "cells": p.get("cells") or [],
        } for p in players],
    }


@_public
def match_detail(match_id: str) -> dict | None:
    """Ficha completa de un partido. None si el id no existe."""
    rec = _base_by_id().get(match_id)
    if rec is None:
        return None
    feat = _feature_by_id().get(match_id, {})
    stats = _stats_by_key()
    hs, as_ = stats.get((match_id, "home"), {}), stats.get((match_id, "away"), {})
    folder = Path(rec["pitch_dir"]) if rec["pitch_dir"] else None

    home_id = None
    if folder is not None and (folder / "match.json").is_file():
        home_id = ((_read_json(folder / "match.json") or {}).get("home_team") or {}).get("id")

    shots = _read_shots(folder, home_id) if folder is not None else []
    momentum = _read_momentum(folder) if folder is not None else []
    events = _read_events(folder, home_id) if folder is not None else []
    lineups = _read_lineups(folder) if folder is not None else None
    heatmaps = _read_heatmaps(folder, home_id) if folder is not None else None

    adv_home = {k: hs.get(col) for k, col in ADV_SPEC.items()}
    adv_away = {k: as_.get(col) for k, col in ADV_SPEC.items()}
    has_adv = any(v is not None and not pd.isna(v) for v in (*adv_home.values(), *adv_away.values()))

    stats_out = []
    for key, label, group, col in STAT_SPEC:
        stats_out.append({"key": key, "label": label, "group": group,
                          "home": hs.get(col), "away": as_.get(col)})

    return {
        "match": _match_item(rec),
        "pre_match": {
            "home": _pre_match("home", rec["home"], match_id, feat),
            "away": _pre_match("away", rec["away"], match_id, feat),
            "market": {
                "pre": {"home": feat.get("mkt_p_home"), "draw": feat.get("mkt_p_draw"),
                        "away": feat.get("mkt_p_away")},
                "close": {"home": feat.get("close_p_home"), "draw": feat.get("close_p_draw"),
                          "away": feat.get("close_p_away")},
                "overround": feat.get("mkt_overround"),
                "odds": {"home": feat.get("mkt_odds_home"), "draw": feat.get("mkt_odds_draw"),
                         "away": feat.get("mkt_odds_away")} if pd.notna(feat.get("mkt_odds_home")) else None,
            },
            "model": ({"name": SHOWN_MODEL, "probs": _model_by_id()[match_id]}
                      if match_id in _model_by_id() else None),
        },
        "stats": stats_out,
        "shots": shots,
        "momentum": momentum,
        "events": events,
        "lineups": lineups,
        "heatmaps": heatmaps,
        "advanced": {"home": adv_home, "away": adv_away} if has_adv else None,
    }


@_public
def team(league: str, team_name: str, season: int | None = None) -> dict | None:
    """Ficha de equipo: partidos de la temporada, serie histórica y resumen. None si no existe."""
    if league not in LEAGUES:
        return None
    b = _base()
    tm = b[(b.league == league) & ((b.home == team_name) | (b.away == team_name))]
    if tm.empty:
        return None
    season = int(tm.season.max()) if season is None else int(season)
    sub = tm[tm.season == season]
    if sub.empty:
        return None
    feat = _feature_by_id()

    matches_out = []
    pts = gf = ga = 0
    xg_for_vals, xg_against_vals = [], []
    for r in sub.itertuples(index=False):
        home_venue = r.home == team_name
        gf_i, ga_i = (int(r.home_goals), int(r.away_goals)) if home_venue else (int(r.away_goals), int(r.home_goals))
        xf, xa = (r.home_xg, r.away_xg) if home_venue else (r.away_xg, r.home_xg)
        letter = _letter(gf_i, ga_i)
        pts += {"W": 3, "D": 1, "L": 0}[letter]
        gf += gf_i
        ga += ga_i
        if _nn(xf) is not None:
            xg_for_vals.append(float(xf))
        if _nn(xa) is not None:
            xg_against_vals.append(float(xa))
        f = feat.get(r.match_id, {})
        matches_out.append({
            "match_id": r.match_id,
            "kickoff": r.kickoff,
            "opponent": r.away if home_venue else r.home,
            "venue": "H" if home_venue else "A",
            "gf": gf_i,
            "ga": ga_i,
            "xg_for": _nn(xf),
            "xg_against": _nn(xa),
            "result": letter,
            "elo_before": f.get("home_elo" if home_venue else "away_elo"),
        })

    series = []
    for r in tm.itertuples(index=False):
        f = feat.get(r.match_id, {})
        side = "home" if r.home == team_name else "away"
        series.append({
            "kickoff": r.kickoff,
            "ewm_xg_for": f.get(f"{side}_ewm_xg_for"),
            "ewm_xg_against": f.get(f"{side}_ewm_xg_against"),
            "elo": f.get(f"{side}_elo"),
        })

    return {
        "team": team_name,
        "league": league,
        "season": season,
        "matches": matches_out,
        "series": series,
        "summary": {
            "played": len(sub),
            "pts": pts,
            "gf": gf,
            "ga": ga,
            "xg_for": sum(xg_for_vals) if xg_for_vals else None,
            "xg_against": sum(xg_against_vals) if xg_against_vals else None,
        },
    }


def _months(start: datetime, end: datetime) -> list[str]:
    out, y, m = [], start.year, start.month
    while (y, m) <= (end.year, end.month):
        out.append(f"{y}{m:02d}")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


TEST_SEASONS = (2025, 2026)
MARKET_MODEL = "Mercado pre-cierre"


def _calibration(p: np.ndarray, y: np.ndarray, edges=np.arange(0, 0.9, 0.1)) -> list:
    """Tramos de probabilidad predicha frente a frecuencia observada (las tres salidas juntas)."""
    out = []
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = (p >= lo) & (p < hi)
        n = int(m.sum())
        if n < 30:
            continue
        f = float(y[m].mean())
        se = 1.96 * math.sqrt(f * (1 - f) / n)
        out.append({"p": float(p[m].mean()), "freq": f, "n": n, "lo": f - se, "hi": f + se})
    return out


@_public
@functools.lru_cache(maxsize=1)
def model_eval() -> dict | None:
    """Evaluación real fuera de muestra (test 2025/26–2026/27): ranking, ligas, calibración y apuestas."""
    report_path = PROCESSED / "model_report.json"
    preds_path = PROCESSED / "model_predictions.parquet"
    if not report_path.is_file() or not preds_path.is_file():
        return None
    report = json.loads(report_path.read_bytes())
    table_key = next((k for k in report.get("tablas", {}) if k.startswith("test")), None)
    ranking = [{"model": r["modelo"], "n": r["n"], "logloss": r["logloss"], "rps": r["rps"], "brier": r["brier"],
                "vs_market": r["vs_mercado"], "ci": [r["ic_lo"], r["ic_hi"]]}
               for r in report["tablas"].get(table_key, [])]

    df = pd.read_parquet(preds_path)
    df = df[df.season.isin(TEST_SEASONS)]
    keys = ("home", "draw", "away")
    onehot = np.eye(3)[df["result"].to_numpy().astype(int)]

    def probs(name):
        return df[[f"{name}|p_{k}" for k in keys]].to_numpy()

    def metrics(p, y):
        ll = float(-np.log(np.clip((p * y).sum(1), 1e-12, 1)).mean())
        brier = float(((p - y) ** 2).sum(1).mean())
        rps = float((((np.cumsum(p, 1) - np.cumsum(y, 1))[:, :2]) ** 2).sum(1).mean() / 2)
        return {"logloss": ll, "brier": brier, "rps": rps}

    pm, pk = probs(SHOWN_MODEL), probs(MARKET_MODEL)
    ok = ~(np.isnan(pm).any(1) | np.isnan(pk).any(1))
    leagues = []
    for code in [None, *LEAGUES]:
        m = ok & ((df.league == code).to_numpy() if code else True)
        if m.sum() == 0:
            continue
        leagues.append({"league": code, "n": int(m.sum()),
                        "model": metrics(pm[m], onehot[m]), "market": metrics(pk[m], onehot[m])})

    bets = [{"model": k, "bets": v["apuestas"], "roi": v["roi"], "roi_ci": v["roi_ic"]}
            for k, v in report.get("apuestas_test", {}).items()]
    return {
        "model": SHOWN_MODEL,
        "market": MARKET_MODEL,
        "seasons": list(TEST_SEASONS),
        "ranking": ranking,
        "leagues": leagues,
        "calibration": {"model": _calibration(pm[ok].ravel(), onehot[ok].ravel()),
                        "market": _calibration(pk[ok].ravel(), onehot[ok].ravel())},
        "bets": bets,
    }


@_public
@functools.lru_cache(maxsize=1)
def markets() -> dict | None:
    """Casas de apuestas frente a Polymarket en los mismos partidos: margen cobrado y precisión."""
    path = PROCESSED / "polymarket.parquet"
    if not path.is_file():
        return None
    pm = pd.read_parquet(path, columns=["match_id", "pm_pre_home", "pm_pre_draw", "pm_pre_away"]).dropna()
    feat = _feature_frame()[["match_id", "mkt_overround"]].dropna()
    both = pm.merge(feat, on="match_id")
    books = both["mkt_overround"].to_numpy()
    poly = (both["pm_pre_home"] + both["pm_pre_draw"] + both["pm_pre_away"] - 1).to_numpy()
    edges = np.round(np.arange(-0.03, 0.1001, 0.0025), 4)

    def hist(values):
        counts, _ = np.histogram(np.clip(values, edges[0], edges[-1] - 1e-9), bins=edges)
        return counts.tolist()

    report_path = PROCESSED / "polymarket_report.json"
    report = json.loads(report_path.read_bytes()) if report_path.is_file() else {}
    accuracy = [{"source": r["fuente"], "n": r["n"], "logloss": r["logloss"]}
                for r in report.get("precision", {}).get("pre", [])]
    return {
        "n": int(len(both)),
        "edges": edges.tolist(),
        "books": {"mean": float(books.mean()), "hist": hist(books)},
        "polymarket": {"mean": float(poly.mean()), "hist": hist(poly)},
        "all_books_mean": float(feat["mkt_overround"].mean()),
        "all_books_n": int(len(feat)),
        "accuracy": accuracy,
    }


@_public
def upcoming(days: int = 21) -> list:
    """Partidos programados entre ahora y `days` días, con cuotas si fixtures.csv las trae y
    probabilidades de SHOWN_MODEL calculadas solo con partidos ya jugados."""
    now = datetime.now(timezone.utc)
    end = now + timedelta(days=int(days))
    names = _espn_names()
    markets = _fixture_markets()
    state = _upcoming_state()
    found: dict[tuple, dict] = {}
    for league in LEAGUES:
        for ym in _months(now, end):
            path = ESPN_SCOREBOARD / league / f"{ym}.json"
            if not path.is_file():
                continue
            for ev in json.loads(path.read_bytes()).get("events") or []:
                comp = ev["competitions"][0]
                if comp["status"]["type"]["name"] != "STATUS_SCHEDULED":
                    continue
                kickoff = pd.Timestamp(ev["date"])
                kickoff = kickoff.tz_localize("UTC") if kickoff.tzinfo is None else kickoff.tz_convert("UTC")
                if not (now <= kickoff <= end):
                    continue
                sides = {c["homeAway"]: c["team"]["displayName"] for c in comp["competitors"]}
                home = names.get((league, sides["home"]), sides["home"])
                away = names.get((league, sides["away"]), sides["away"])
                local_date = kickoff.tz_convert("Europe/London").date()
                found[(league, ev["id"])] = {
                    "league": league,
                    "kickoff": _iso(kickoff),
                    "home": home,
                    "away": away,
                    "espn_id": ev["id"],
                    "market": markets.get((league, local_date, home, away)),
                    "model": elo_forecast(state, home, away, kickoff) if state else None,
                }
    return sorted(found.values(), key=lambda x: x["kickoff"])
