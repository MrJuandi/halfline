"""Analizador de equipo por temporada: plantilla, once tipo, formaciones, impacto on/off,
perfil de estilo frente a la liga y tiros de toda la temporada.

Fuente: ficheros crudos de PitchAPI de cada partido (players, lineups, events, shots, match)
y data/processed/team_match_stats.parquet para el estilo.

Impacto on/off: para cada jugador, diferencia de xG (a favor − en contra) por 90 minutos del
equipo con él en el campo frente a sin él. Los intervalos salen de las alineaciones y de los
cambios; las expulsiones no se descuentan. Es descriptivo: no aísla el efecto del jugador de
los rivales, el marcador o los compañeros con los que coincide.
"""
from __future__ import annotations

import functools
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

from futdata.web_data import _base, _clean, _pitch_dir, _read_json, _stats_frame

MIN_IMPACT_MINUTES = 270  # minutos mínimos (con y sin el jugador) para mostrar su impacto
MATCH_LENGTH = 95         # duración aproximada de un partido con descuento

PLAYER_KEYS = {  # clave de PitchAPI -> nombre en la salida (se suman por partido)
    "minutes_played": "minutes", "goals": "goals", "assists": "assists",
    "expected_goals": "xg", "expected_goals_non_penalty": "npxg", "expected_assists": "xa",
    "total_shots": "shots", "ShotsOnTarget": "shots_on_target", "chances_created": "chances",
    "touches": "touches", "touches_opp_box": "box_touches", "dribbles_succeeded": "dribbles",
    "matchstats.headers.tackles": "tackles", "interceptions": "interceptions",
    "recoveries": "recoveries", "duel_won": "duels_won", "duel_lost": "duels_lost",
    "passes_into_final_third": "final_third_passes", "accurate_passes": "accurate_passes",
    "saves": "saves", "goals_prevented": "goals_prevented", "goals_conceded": "goals_conceded",
}

STYLE = [  # (columna de team_match_stats, etiqueta, más alto es "más", lado)
    ("pa_possession", "Posesión", "own"),
    ("pa_passes", "Pases por partido", "own"),
    ("pa_accurate_passes_pct", "Precisión de pase", "own"),
    ("pa_expected_goals", "xG generado", "own"),
    ("pa_total_shots", "Tiros", "own"),
    ("pa_big_chance", "Grandes ocasiones", "own"),
    ("pa_touches_opp_box", "Toques en el área rival", "own"),
    ("pa_corners", "Córners", "own"),
    ("pa_dribbles_succeeded", "Regates", "own"),
    ("pa_expected_goals", "xG concedido", "opp"),
    ("pa_total_shots", "Tiros concedidos", "opp"),
    ("pa_tackles", "Entradas", "own"),
    ("pa_interceptions", "Intercepciones", "own"),
    ("pa_duel_won", "Duelos ganados", "own"),
    ("pa_fouls", "Faltas", "own"),
    ("adv_ppda", "PPDA (presión: menos = más)", "own"),
    ("adv_field_tilt", "Field tilt", "own"),
]


def _role(x: float) -> str:
    """Línea a partir de la posición media de salida (0 = portería propia, 1 = rival)."""
    if x <= 0.15:
        return "POR"
    if x <= 0.42:
        return "DEF"
    if x <= 0.68:
        return "MED"
    return "DEL"


def _value(stat) -> float | None:
    if not isinstance(stat, dict):
        return None
    v = stat.get("value")
    return float(v) if isinstance(v, (int, float)) else None


def _player_stats(entry: dict) -> dict:
    out = {}
    for group in entry.get("stats") or []:
        for item in (group.get("stats") or {}).values():
            key = PLAYER_KEYS.get(item.get("key"))
            if key and key not in out:
                v = _value(item.get("stat"))
                if v is not None:
                    out[key] = v
            if item.get("key") == "rating_title" and "rating" not in out:
                v = _value(item.get("stat"))
                if v is not None:
                    out["rating"] = v
    return out


def _intervals(starters: list, events: list, team_id: str, end: float) -> dict:
    """{player_id: [(desde, hasta), ...]} minutos en el campo según titulares y cambios."""
    on: dict[str, float] = {p["player_id"]: 0.0 for p in starters if p.get("player_id")}
    spans: dict[str, list] = defaultdict(list)
    subs = sorted(
        (e for e in events if e.get("event_type") == "substitution" and e.get("team_id") == team_id),
        key=lambda e: (e.get("minute") or 0) + (e.get("minute_added") or 0) / 100,
    )
    for e in subs:
        t = float(e.get("minute") or 0) + float(e.get("minute_added") or 0)
        out_id = (e.get("player") or {}).get("id")
        in_id = (e.get("sub_in_player") or {}).get("id")
        if out_id in on:
            spans[out_id].append((on.pop(out_id), t))
        if in_id:
            on[in_id] = t
    for pid, start in on.items():
        spans[pid].append((start, max(end, start)))
    return spans


@functools.lru_cache(maxsize=256)
def _analysis(league: str, team: str, season: int):
    b = _base()
    sub = b[(b.league == league) & (b.season == season) & ((b.home == team) | (b.away == team))]
    if sub.empty:
        return None

    players: dict[str, dict] = {}
    start_pos: dict[str, list] = defaultdict(list)
    formations: list[tuple[str, str]] = []
    slots: dict[str, Counter] = defaultdict(Counter)  # formación -> (puesto, jugador) -> partidos
    shots_for: list[dict] = []
    shots_against: list[dict] = []
    goals_by_bin = {"for": [0] * 6, "against": [0] * 6}
    impact_acc: dict[str, dict] = defaultdict(lambda: {"on_min": 0.0, "xgf_on": 0.0, "xga_on": 0.0, "gf_on": 0, "ga_on": 0})
    team_tot = {"min": 0.0, "xgf": 0.0, "xga": 0.0, "gf": 0, "ga": 0}
    n_matches = 0

    for r in sub.itertuples(index=False):
        folder = _pitch_dir(r.league, r.season, r.pitchapi_id)
        if folder is None:
            continue
        info = _read_json(folder / "match.json")
        lineups = _read_json(folder / "lineups.json") or {}
        if not info:
            continue
        is_home = r.home == team
        team_id = info["home_team"]["id"] if is_home else info["away_team"]["id"]
        side = "home" if is_home else "away"
        letter = "W" if (r.home_goals - r.away_goals) * (1 if is_home else -1) > 0 else (
            "D" if r.home_goals == r.away_goals else "L")
        n_matches += 1

        lineup = lineups.get(side) or {}
        starters = lineup.get("starters") or []
        if lineup.get("formation"):
            formations.append((lineup["formation"], letter))
            for p in starters:
                if p.get("player_id") and p.get("pitch_x") is not None:
                    slot = (round(float(p["pitch_x"]), 2), round(float(p["pitch_y"]), 2))
                    slots[lineup["formation"]][(slot, p["player_id"])] += 1
        for p in starters:
            pid = p.get("player_id")
            if pid and p.get("pitch_x") is not None:
                start_pos[pid].append((float(p["pitch_x"]), float(p["pitch_y"]), p.get("shirt_number")))

        # Estadísticas por jugador
        for entry in _read_json(folder / "players.json") or []:
            if entry.get("team_id") != team_id:
                continue
            pl = entry.get("player") or {}
            pid = pl.get("id")
            if not pid:
                continue
            st = _player_stats(entry)
            if not st.get("minutes"):
                continue
            agg = players.setdefault(pid, {"id": pid, "name": pl.get("name"), "photo": pl.get("image_url"),
                                           "apps": 0, "starts": 0, "rating_sum": 0.0, "rating_min": 0.0})
            agg["apps"] += 1
            for k, v in st.items():
                if k == "rating":
                    agg["rating_sum"] += v * st["minutes"]
                    agg["rating_min"] += st["minutes"]
                else:
                    agg[k] = agg.get(k, 0.0) + v
        for p in starters:
            if p.get("player_id") in players:
                players[p["player_id"]]["starts"] += 1

        # Tiros y goles por tramo de minutos
        events = (_read_json(folder / "events.json") or {}).get("events") or []
        shots = []
        for period in (_read_json(folder / "shots.json") or {}).get("periods") or []:
            shots.extend(period.get("shots") or [])
        end = max([MATCH_LENGTH] + [float(s.get("minute") or 0) + 1 for s in shots])
        xgf = xga = 0.0
        for s in shots:
            own = s.get("team_id") == team_id
            xg = float(s.get("expected_goals") or 0)
            goal = s.get("event_type") == "Goal"
            item = {"x": s.get("x"), "y": s.get("y"), "xg": round(xg, 3), "goal": goal,
                    "player": (s.get("player") or {}).get("name"), "minute": s.get("minute"),
                    "match_id": r.match_id}
            (shots_for if own else shots_against).append(item)
            if own:
                xgf += xg
            else:
                xga += xg
        for e in events:
            if e.get("event_type") != "goal":
                continue
            scorer_team = e.get("team_id")
            bucket = min(5, int((e.get("minute") or 0) // 15))
            # gol en propia: el evento va con el equipo del jugador que lo marca
            own_goal = bool(e.get("is_own_goal"))
            ours = (scorer_team == team_id) != own_goal
            goals_by_bin["for" if ours else "against"][bucket] += 1

        # Impacto on/off
        gf, ga = (r.home_goals, r.away_goals) if is_home else (r.away_goals, r.home_goals)
        team_tot["min"] += end
        team_tot["xgf"] += xgf
        team_tot["xga"] += xga
        team_tot["gf"] += int(gf)
        team_tot["ga"] += int(ga)
        goal_minutes = [(float(e.get("minute") or 0), (e.get("team_id") == team_id) != bool(e.get("is_own_goal")))
                        for e in events if e.get("event_type") == "goal"]
        for pid, spans in _intervals(starters, events, team_id, end).items():
            acc = impact_acc[pid]
            for a, z in spans:
                acc["on_min"] += z - a
                for s in shots:
                    m = float(s.get("minute") or 0)
                    if a <= m < z or (z >= end and m >= a):
                        if s.get("team_id") == team_id:
                            acc["xgf_on"] += float(s.get("expected_goals") or 0)
                        else:
                            acc["xga_on"] += float(s.get("expected_goals") or 0)
                for m, ours in goal_minutes:
                    if a <= m < z or (z >= end and m >= a):
                        acc["gf_on" if ours else "ga_on"] += 1

    if not n_matches:
        return None

    # Plantilla
    squad = []
    for pid, p in players.items():
        pos = start_pos.get(pid, [])
        avg_x = float(np.mean([q[0] for q in pos])) if pos else None
        avg_y = float(np.mean([q[1] for q in pos])) if pos else None
        number = Counter(q[2] for q in pos if q[2]).most_common(1)[0][0] if pos else None
        row = {k: v for k, v in p.items() if k not in ("rating_sum", "rating_min")}
        row["rating"] = p["rating_sum"] / p["rating_min"] if p["rating_min"] else None
        row["role"] = _role(avg_x) if avg_x is not None else ("POR" if p.get("saves") else None)
        row["avg_x"], row["avg_y"], row["number"] = avg_x, avg_y, number
        imp = impact_acc.get(pid)
        if imp and imp["on_min"] >= MIN_IMPACT_MINUTES and team_tot["min"] - imp["on_min"] >= MIN_IMPACT_MINUTES:
            off_min = team_tot["min"] - imp["on_min"]
            on_xgd = (imp["xgf_on"] - imp["xga_on"]) / imp["on_min"] * 90
            off_xgd = ((team_tot["xgf"] - imp["xgf_on"]) - (team_tot["xga"] - imp["xga_on"])) / off_min * 90
            row["impact"] = {
                "on_minutes": imp["on_min"], "off_minutes": off_min,
                "xgf90_on": imp["xgf_on"] / imp["on_min"] * 90,
                "xga90_on": imp["xga_on"] / imp["on_min"] * 90,
                "xgf90_off": (team_tot["xgf"] - imp["xgf_on"]) / off_min * 90,
                "xga90_off": (team_tot["xga"] - imp["xga_on"]) / off_min * 90,
                "xgd90_on": on_xgd, "xgd90_off": off_xgd, "delta": on_xgd - off_xgd,
                "goals_on": [imp["gf_on"], imp["ga_on"]],
            }
        else:
            row["impact"] = None
        squad.append(row)
    squad.sort(key=lambda p: -p.get("minutes", 0))

    # Once tipo: en la formación más usada, el jugador que más veces ocupó cada puesto
    by_id = {p["id"]: p for p in squad}
    typical_xi = []
    top_formation = Counter(f for f, _ in formations).most_common(1)
    if top_formation:
        counts = slots[top_formation[0][0]]
        slot_total: Counter = Counter()
        for (slot, _), n in counts.items():
            slot_total[slot] += n
        used: set = set()
        for slot, _ in slot_total.most_common(11):
            for (sl, pid), n in sorted(counts.items(), key=lambda kv: -kv[1]):
                if sl == slot and pid not in used and pid in by_id:
                    used.add(pid)
                    p = by_id[pid]
                    typical_xi.append({"id": pid, "name": p["name"], "number": p["number"], "x": slot[0],
                                       "y": slot[1], "starts": p["starts"], "slot_starts": n,
                                       "role": _role(slot[0]), "photo": p["photo"]})
                    break

    form_count = Counter(f for f, _ in formations)
    formation_rows = []
    for f, n in form_count.most_common():
        res = [l for g, l in formations if g == f]
        pts = sum({"W": 3, "D": 1, "L": 0}[l] for l in res)
        formation_rows.append({"formation": f, "matches": n, "ppg": pts / n,
                               "w": res.count("W"), "d": res.count("D"), "l": res.count("L")})

    return {
        "team": team, "league": league, "season": season, "matches": n_matches,
        "squad": squad, "typical_xi": typical_xi,
        "typical_formation": top_formation[0][0] if top_formation else None, "formations": formation_rows,
        "shots": {"for": shots_for, "against": shots_against},
        "goals_by_15": goals_by_bin,
        "totals": team_tot,
        "style": _style(league, season, team),
        "impact_min_minutes": MIN_IMPACT_MINUTES,
    }


def _style(league: str, season: int, team: str) -> list:
    """Media por partido de cada métrica y percentil frente al resto de equipos de la liga."""
    st = _stats_frame()
    b = _base()[["match_id", "league", "season"]]
    cols = sorted({c for c, _, _ in STYLE if c in st.columns})
    rows = st.merge(b, on="match_id")
    rows = rows[(rows.league == league) & (rows.season == season)]
    opp = rows[["match_id", "side"] + cols].copy()
    opp["side"] = opp["side"].map({"home": "away", "away": "home"})
    rows = rows.merge(opp, on=["match_id", "side"], suffixes=("", "__opp"))
    out = []
    for col, label, who in STYLE:
        if col not in st.columns:
            continue
        src = col if who == "own" else f"{col}__opp"
        per_team = rows.groupby("team")[src].mean().dropna()
        if team not in per_team.index or len(per_team) < 5:
            continue
        value = float(per_team[team])
        pct = float((per_team < value).sum() + 0.5 * ((per_team == value).sum() - 1)) / (len(per_team) - 1)
        out.append({"key": f"{col}:{who}", "label": label, "value": value, "pct": pct,
                    "league_avg": float(per_team.mean()), "rank": int((per_team > value).sum() + 1),
                    "teams": int(len(per_team))})
    return out


def team_analysis(league: str, team: str, season: int | None = None) -> dict | None:
    b = _base()
    tm = b[(b.league == league) & ((b.home == team) | (b.away == team))]
    if tm.empty:
        return None
    season = int(tm.season.max()) if season is None else int(season)
    return _clean(_analysis(league, team, season))
