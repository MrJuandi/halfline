"""Estadísticas agregadas por jugador, liga, temporada y equipo (PitchAPI).

Recorre los partidos de data/processed/matches.parquet con pitchapi_id y lee players.json,
lineups.json y match.json de cada uno. Las estadísticas por partido salen de
team_analysis._player_stats (claves de team_analysis.PLAYER_KEYS) y se suman por grupo.

Salida: data/processed/player_seasons.parquet, una fila por jugador-liga-temporada-equipo.
  rating_w   media del rating ponderada por minutos
  avg_x/y    posición media de salida (solo partidos como titular)
  role       línea según team_analysis._role; sin posición media: 'POR' si hay paradas, si no None
  starts     partidos en los que aparece entre los titulares de su equipo

Uso:  python -m futdata.player_seasons
"""
from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor

import pandas as pd

from futdata.matches import PROCESSED
from futdata.team_analysis import PLAYER_KEYS, _player_stats, _role
from futdata.web_data import _pitch_dir, _read_json

OUT = PROCESSED / "player_seasons.parquet"
STAT_COLS = list(PLAYER_KEYS.values())
GROUP_KEYS = ["player_id", "league", "season", "team"]


def _match_rows(job: tuple) -> list[dict]:
    """Filas (una por jugador que juega en el partido) de un partido. Función de nivel de módulo
    para poder ejecutarla en ProcessPoolExecutor."""
    league, season, pitchapi_id, home, away = job
    folder = _pitch_dir(league, season, pitchapi_id)
    if folder is None:
        return []
    info = _read_json(folder / "match.json")
    if not info:
        return []
    side_ids = {"home": info["home_team"]["id"], "away": info["away_team"]["id"]}
    canonical = {"home": home, "away": away}
    lineups = _read_json(folder / "lineups.json") or {}
    starters = {}
    for side in ("home", "away"):
        team_lineup = lineups.get(side) or {}
        starters[side] = {p["player_id"]: p for p in team_lineup.get("starters") or []
                          if p.get("player_id")}

    rows = []
    for entry in _read_json(folder / "players.json") or []:
        side = next((s for s, tid in side_ids.items() if tid == entry.get("team_id")), None)
        if side is None:
            continue
        player = entry.get("player") or {}
        pid = player.get("id")
        if not pid:
            continue
        st = _player_stats(entry)
        if not st.get("minutes"):
            continue
        start = starters[side].get(pid)
        row = {
            "player_id": pid, "name": player.get("name"), "photo": player.get("image_url"),
            "league": league, "season": int(season), "team": canonical[side],
            "apps": 1, "starts": 1 if start else 0,
            "rating": st.get("rating"),
            "start_x": start.get("pitch_x") if start else None,
            "start_y": start.get("pitch_y") if start else None,
        }
        for key in STAT_COLS:
            row[key] = st.get(key)
        rows.append(row)
    return rows


def build() -> pd.DataFrame:
    matches = pd.read_parquet(PROCESSED / "matches.parquet",
                              columns=["league", "season", "pitchapi_id", "home", "away"])
    matches = matches[matches["pitchapi_id"].notna()]
    jobs = [(r.league, int(r.season), r.pitchapi_id, r.home, r.away)
            for r in matches.itertuples(index=False)]

    rows: list[dict] = []
    with ProcessPoolExecutor() as pool:
        for chunk in pool.map(_match_rows, jobs, chunksize=64):
            rows.extend(chunk)
    df = pd.DataFrame(rows)

    # Sumas por grupo (las estadísticas ausentes cuentan como 0)
    grouped = df.groupby(GROUP_KEYS, sort=False)
    agg = grouped.agg(
        name=("name", "last"), photo=("photo", "last"),
        apps=("apps", "sum"), starts=("starts", "sum"),
        **{key: (key, "sum") for key in STAT_COLS},
    )

    # Rating medio ponderado por minutos (solo filas con rating)
    weighted = df.assign(
        _rating_x_min=df["rating"] * df["minutes"],
        _min_with_rating=df["minutes"].where(df["rating"].notna()),
    ).groupby(GROUP_KEYS, sort=False)[["_rating_x_min", "_min_with_rating"]].sum()
    agg["rating_w"] = (weighted["_rating_x_min"] / weighted["_min_with_rating"]).where(
        weighted["_min_with_rating"] > 0)

    # Posición media de salida (solo titulares con posición)
    agg["avg_x"] = grouped["start_x"].mean()
    agg["avg_y"] = grouped["start_y"].mean()

    agg = agg.reset_index()
    agg["role"] = [
        _role(x) if pd.notna(x) else ("POR" if saves and saves > 0 else None)
        for x, saves in zip(agg["avg_x"], agg["saves"])
    ]
    agg["role"] = agg["role"].astype(object)
    agg["apps"] = agg["apps"].astype(int)
    agg["starts"] = agg["starts"].astype(int)
    agg["season"] = agg["season"].astype(int)
    return agg


def main() -> None:
    df = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUT, index=False)
    print(f"Escrito {OUT}")
    print(f"Filas: {len(df)}")
    print(f"Jugadores únicos: {df['player_id'].nunique()}")
    print(f"Filas con minutes >= 900: {int((df['minutes'] >= 900).sum())}")


if __name__ == "__main__":
    main()
