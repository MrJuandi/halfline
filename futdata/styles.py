"""Estilos de juego: PCA y arquetipos de equipo a partir de estadísticas por partido.

Cada equipo-temporada (mínimo MIN_MATCHES partidos) se describe con ~19 métricas de estilo
(medias por partido o proporciones). Se estandarizan sobre todas las ligas y temporadas, se
reducen con PCA (los dos primeros ejes explican ~60 % de la varianza) y se agrupan con k-means
en arquetipos. Los nombres de los arquetipos se asignan por reglas sobre los centroides para que
no dependan del orden en que k-means numera los grupos.

Salida: data/processed/styles.json
Uso:    python -m futdata.styles
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

from futdata.common import log, utcnow
from futdata.matches import PROCESSED

MIN_MATCHES = 8
N_ARCHETYPES = 6

FEATURES = {  # clave -> (etiqueta, descripción corta)
    "posesion": ("Posesión", "% de posesión"),
    "pases": ("Pases", "pases por partido"),
    "precision": ("Precisión de pase", "% de pases acertados"),
    "directo": ("Juego directo", "% de pases acertados que son balones largos"),
    "centros": ("Centros", "centros acertados por partido"),
    "territorio": ("Territorio", "% de pases en campo rival"),
    "tiros": ("Tiros", "tiros por partido"),
    "tiros_lejanos": ("Tiro lejano", "% de tiros desde fuera del área"),
    "xg": ("xG generado", "xG por partido"),
    "xg_por_tiro": ("Calidad de tiro", "xG por tiro"),
    "balon_parado": ("Balón parado", "% del xG a balón parado"),
    "toques_area": ("Toques en el área", "toques en el área rival por partido"),
    "regates": ("Regates", "regates completados por partido"),
    "xg_contra": ("xG concedido", "xG del rival por partido"),
    "tiros_contra": ("Tiros concedidos", "tiros del rival por partido"),
    "ppda": ("Pasividad sin balón", "pases del rival por acción defensiva (más = presiona menos)"),
    "duelos_aereos": ("Juego aéreo", "duelos aéreos ganados por partido"),
    "despejes": ("Despejes", "despejes por partido"),
    "faltas": ("Faltas", "faltas por partido"),
}

ARCHETYPE_TEXT = {
    "dominio": ("Dominio total", "Tienen el balón, viven en campo rival y generan muchísimo. Conceden poco porque el rival casi no llega."),
    "control": ("Control y llegada", "Posesión alta y precisa, pocos balones largos y tiros de calidad. Dominan sin la intensidad de la élite."),
    "directo": ("Juego directo", "Balón largo, duelos y faltas. Poca posesión y poca precisión; buscan ganar la segunda jugada."),
    "aereo": ("Físicos de área", "Fuertes por arriba en las dos áreas: muchos despejes, duelos aéreos y peso del balón parado en su xG."),
    "sufridor": ("Bloque que sufre", "Defienden lejos de la portería rival y conceden mucho; llegan poco al área y abusan del tiro lejano."),
    "equilibrio": ("Presión y orden", "Presionan más que la media y conceden poco, con la posesión repartida. Sólidos sin dominar el balón."),
}
ARCHETYPE_COLOR = {
    "dominio": "#4cc38a", "control": "#5b9bf0", "directo": "#e5a54b",
    "aereo": "#b583e6", "sufridor": "#e5616b", "equilibrio": "#8e9096",
}


WINDOW = 10        # partidos de la ventana móvil del «estado actual»
MIN_WINDOW = 5     # mínimo para mostrar un equipo en la ventana (con aviso si < WINDOW)


def _team_matches() -> pd.DataFrame:
    """Una fila por equipo y partido con sus estadísticas, las del rival (_opp) y la hora."""
    st = pd.read_parquet(PROCESSED / "team_match_stats.parquet")
    cols = ["pa_possession", "pa_passes", "pa_accurate_passes_pct", "pa_long_balls_accurate",
            "pa_accurate_passes", "pa_accurate_crosses", "pa_opposition_half_passes", "pa_total_shots",
            "pa_shots_outside_box", "pa_expected_goals", "pa_expected_goals_set_play",
            "pa_touches_opp_box", "pa_dribbles_succeeded", "pa_tackles", "pa_interceptions",
            "pa_fouls", "pa_aerials_won", "pa_clearances"]
    opp = st[["match_id", "side"] + cols].copy()
    opp["side"] = opp["side"].map({"home": "away", "away": "home"})
    x = st.merge(opp, on=["match_id", "side"], suffixes=("", "_opp"))
    x["kickoff"] = x["kickoff_utc"].fillna(x["date"].dt.tz_localize("UTC") + pd.Timedelta(hours=15))
    return x


def _aggregate(g) -> pd.DataFrame:
    """Las 19 métricas de estilo a partir de un groupby sobre _team_matches()."""
    return pd.DataFrame({
        "posesion": g.pa_possession.mean(),
        "pases": g.pa_passes.mean(),
        "precision": g.pa_accurate_passes_pct.mean(),
        "directo": g.pa_long_balls_accurate.sum() / g.pa_accurate_passes.sum() * 100,
        "centros": g.pa_accurate_crosses.mean(),
        "territorio": g.pa_opposition_half_passes.sum() / g.pa_passes.sum() * 100,
        "tiros": g.pa_total_shots.mean(),
        "tiros_lejanos": g.pa_shots_outside_box.sum() / g.pa_total_shots.sum() * 100,
        "xg": g.pa_expected_goals.mean(),
        "xg_por_tiro": g.pa_expected_goals.sum() / g.pa_total_shots.sum(),
        "balon_parado": g.pa_expected_goals_set_play.sum() / g.pa_expected_goals.sum() * 100,
        "toques_area": g.pa_touches_opp_box.mean(),
        "regates": g.pa_dribbles_succeeded.mean(),
        "xg_contra": g.pa_expected_goals_opp.mean(),
        "tiros_contra": g.pa_total_shots_opp.mean(),
        "ppda": g.pa_passes_opp.sum() / (g.pa_tackles.sum() + g.pa_interceptions.sum() + g.pa_fouls.sum()),
        "duelos_aereos": g.pa_aerials_won.mean(),
        "despejes": g.pa_clearances.mean(),
        "faltas": g.pa_fouls.mean(),
        "partidos": g.size(),
    }).reset_index()


def team_season_features() -> pd.DataFrame:
    """Temporadas completas. La temporada en curso queda fuera: se representa con la ventana
    móvil de current_window_features()."""
    x = _team_matches()
    x = x[x.season < x.season.max()]
    f = _aggregate(x.groupby(["league", "season", "team"]))
    return f[f.partidos >= MIN_MATCHES].reset_index(drop=True)


def current_window_features(window: int = WINDOW) -> pd.DataFrame:
    """Estado actual: últimos `window` partidos de liga de cada equipo que juega la temporada en
    curso (la ventana puede incluir partidos de la temporada anterior)."""
    x = _team_matches()
    now = int(x.season.max())
    teams = x[x.season == now][["league", "team"]].drop_duplicates()
    x = x.merge(teams, on=["league", "team"]).sort_values("kickoff")
    last = x.groupby(["league", "team"]).tail(window)
    f = _aggregate(last.groupby(["league", "team"]))
    info = last.groupby(["league", "team"]).agg(
        desde=("kickoff", "min"), hasta=("kickoff", "max"),
        de_esta_temporada=("season", lambda s: int((s == now).sum())))
    f = f.merge(info.reset_index(), on=["league", "team"])
    f["season"] = now
    return f[f.partidos >= MIN_WINDOW].reset_index(drop=True)


def _name_archetypes(centroids: pd.DataFrame) -> dict[int, str]:
    """Reglas sobre los centroides (en desviaciones típicas) para nombrar cada grupo."""
    left = set(centroids.index)
    names: dict[int, str] = {}

    def take(key: str, score: pd.Series):
        best = score.loc[sorted(left)].idxmax()
        names[best] = key
        left.discard(best)

    c = centroids
    take("dominio", c.xg + c.pases - c.tiros_contra)
    take("directo", c.directo + c.faltas - c.precision)
    take("aereo", c.despejes + c.duelos_aereos + c.balon_parado)
    take("sufridor", c.xg_contra + c.tiros_contra - c.toques_area)
    take("control", c.precision + c.xg_por_tiro - c.directo)
    for i in left:
        names[i] = "equilibrio"
    return names


def build() -> dict:
    f = team_season_features()
    keys = list(FEATURES)
    scaler = StandardScaler().fit(f[keys])
    z = pd.DataFrame(scaler.transform(f[keys]), columns=keys)
    pca = PCA(n_components=4, random_state=0).fit(z)
    pcs = pca.transform(z)
    # Orientación estable: el eje 1 crece con la posesión; el eje 2, con los centros.
    signs = np.array([np.sign(pca.components_[0][keys.index("posesion")]) or 1,
                      np.sign(pca.components_[1][keys.index("centros")]) or 1, 1, 1])
    pcs = pcs * signs
    comps = pca.components_ * signs[:, None]

    km = KMeans(N_ARCHETYPES, n_init=50, random_state=0).fit(z)
    centroids = pd.DataFrame(km.cluster_centers_, columns=keys)
    names = _name_archetypes(centroids)

    f["pc1"], f["pc2"], f["pc3"] = pcs[:, 0], pcs[:, 1], pcs[:, 2]
    f["archetype"] = [names[i] for i in km.labels_]
    # Tipicidad: distancia al centro del arquetipo (menor = más típico)
    f["dist"] = np.linalg.norm(z.to_numpy() - km.cluster_centers_[km.labels_], axis=1)

    axes = []
    for i, name in enumerate(["Dominio del partido", "Juego por fuera y físico"]):
        load = pd.Series(comps[i], index=keys).sort_values()
        axes.append({
            "name": name, "explained": float(pca.explained_variance_ratio_[i]),
            "positive": [FEATURES[k][0] for k in load.index[::-1][:4]],
            "negative": [FEATURES[k][0] for k in load.index[:4]],
            "loadings": {k: float(v) for k, v in load.items()},
        })

    archetypes = []
    for i in range(N_ARCHETYPES):
        key = names[i]
        members = f[f.archetype == key].sort_values("dist")
        cz = centroids.loc[i]
        archetypes.append({
            "key": key, "name": ARCHETYPE_TEXT[key][0], "description": ARCHETYPE_TEXT[key][1],
            "color": ARCHETYPE_COLOR[key], "size": int(len(members)),
            "traits_high": [FEATURES[k][0] for k in cz.sort_values(ascending=False).index[:3]],
            "traits_low": [FEATURES[k][0] for k in cz.sort_values().index[:3]],
            "centroid": {k: float(v) for k, v in cz.items()},
            "typical": [{"team": r.team, "league": r.league, "season": int(r.season)} for r in members.head(6).itertuples()],
            "pc": [float(members.pc1.mean()), float(members.pc2.mean())],
        })

    zf = z.copy()
    zf[["league", "season", "team"]] = f[["league", "season", "team"]]
    teams = []
    for idx, r in f.iterrows():
        same = f[(f.season == r.season) & (f.index != idx)]
        dist = np.linalg.norm(z.loc[same.index].to_numpy() - z.loc[idx].to_numpy(), axis=1)
        near = same.assign(d=dist).nsmallest(3, "d")
        teams.append({
            "league": r.league, "season": int(r.season), "team": r.team, "matches": int(r.partidos),
            "pc1": float(r.pc1), "pc2": float(r.pc2), "pc3": float(r.pc3), "archetype": r.archetype,
            "values": {k: float(r[k]) for k in keys},
            "z": {k: float(z.loc[idx, k]) for k in keys},
            "similar": [{"team": n.team, "league": n.league, "distance": float(n.d)} for n in near.itertuples()],
        })

    # Mayores cambios de estilo entre temporadas consecutivas
    movers = []
    for (league, team), g in f.sort_values("season").groupby(["league", "team"]):
        rows = list(g.itertuples())
        for a, b in zip(rows, rows[1:]):
            if b.season != a.season + 1:
                continue
            movers.append({"league": league, "team": team, "from": int(a.season), "to": int(b.season),
                           "distance": float(np.hypot(b.pc1 - a.pc1, b.pc2 - a.pc2)),
                           "path": [[float(a.pc1), float(a.pc2)], [float(b.pc1), float(b.pc2)]],
                           "archetypes": [a.archetype, b.archetype]})
    movers.sort(key=lambda m: -m["distance"])

    # Estado actual (ventana móvil) proyectado con el mismo escalado, PCA y arquetipos
    cur = current_window_features()
    zc = pd.DataFrame(scaler.transform(cur[keys]), columns=keys)
    pc_cur = pca.transform(zc) * signs
    lab_cur = km.predict(zc)
    prev_season = int(cur.season.iloc[0]) - 1 if len(cur) else None
    current = []
    for i, r in cur.iterrows():
        prev = f[(f.league == r.league) & (f.team == r.team) & (f.season == prev_season)]
        dist = np.linalg.norm(z.to_numpy() - zc.loc[i].to_numpy(), axis=1)
        near = f.assign(d=dist)[f.season == prev_season].nsmallest(3, "d")
        current.append({
            "league": r.league, "team": r.team, "season": int(r.season), "matches": int(r.partidos),
            "this_season": int(r.de_esta_temporada), "from": r.desde.isoformat(), "to": r.hasta.isoformat(),
            "short_sample": bool(r.partidos < WINDOW),
            "pc1": float(pc_cur[i, 0]), "pc2": float(pc_cur[i, 1]), "pc3": float(pc_cur[i, 2]),
            "archetype": names[int(lab_cur[i])],
            "values": {k: float(r[k]) for k in keys},
            "z": {k: float(zc.loc[i, k]) for k in keys},
            "prev": ({"pc1": float(prev.pc1.iloc[0]), "pc2": float(prev.pc2.iloc[0]),
                      "archetype": prev.archetype.iloc[0], "season": prev_season} if len(prev) else None),
            "similar": [{"team": n.team, "league": n.league, "distance": float(n.d)} for n in near.itertuples()],
        })

    leagues = (f.groupby("league")[["pc1", "pc2"]].mean().reset_index()
                 .rename(columns={"pc1": "pc1", "pc2": "pc2"}).to_dict("records"))

    out = {
        "generated_at": utcnow(), "min_matches": MIN_MATCHES, "n": int(len(f)),
        "explained": [float(v) for v in pca.explained_variance_ratio_],
        "features": [{"key": k, "label": FEATURES[k][0], "description": FEATURES[k][1]} for k in keys],
        "axes": axes, "archetypes": archetypes, "teams": teams, "movers": movers[:40], "leagues": leagues,
        "current": current, "window": WINDOW,
    }
    PROCESSED.mkdir(parents=True, exist_ok=True)
    (PROCESSED / "styles.json").write_text(json.dumps(out, ensure_ascii=False))
    log.info("styles: %d equipos-temporada, varianza ejes 1-2 = %.1f %%", len(f),
             100 * sum(pca.explained_variance_ratio_[:2]))
    return out


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    o = build()
    print(f"{o['n']} equipos-temporada · ejes 1+2: {100 * sum(o['explained'][:2]):.1f} %")
    for a in o["archetypes"]:
        print(f"  {a['name']:20s} n={a['size']:3d} +{a['traits_high']} −{a['traits_low']} · {[t['team'] + ' ' + str(t['season'] % 100) for t in a['typical'][:4]]}")
    print(f"Estado actual (últimos {WINDOW}): {len(o['current'])} equipos; muestra corta: {sum(c['short_sample'] for c in o['current'])}")
    moved = sorted((c for c in o["current"] if c["prev"]), key=lambda c: -np.hypot(c["pc1"] - c["prev"]["pc1"], c["pc2"] - c["prev"]["pc2"]))
    print("Más cambiados respecto a 25/26:", [(c["team"], c["prev"]["archetype"], c["archetype"]) for c in moved[:6]])
    print("Mayores cambios:", [(m["team"], m["from"], m["to"], round(m["distance"], 1)) for m in o["movers"][:6]])
