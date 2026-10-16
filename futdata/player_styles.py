"""Perfiles de jugador: roles y jugadores parecidos a partir de estadísticas por 90 minutos.

Jugadores de campo con al menos MIN_MINUTES en una temporada. Se describen con 16 rasgos
(producción por 90, acciones defensivas por 90 y posición media: profundidad y amplitud), se
estandarizan, se reducen con PCA para el mapa y se agrupan con k-means en roles. Los nombres de
los roles se asignan por reglas sobre los centroides. «Parecidos» = vecinos más cercanos en el
espacio estandarizado (todas las ligas y temporadas).

Salida: data/processed/player_styles.parquet y data/processed/player_roles.json
Uso:    python -m futdata.player_styles
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

from futdata.common import log
from futdata.matches import PROCESSED

MIN_MINUTES = 900
N_ROLES = 9
WINDOW_MINUTES = 900   # ventana móvil del «estado actual»: últimos 900 minutos jugados
MIN_WINDOW_MINUTES = 450
WINDOW_DAYS = 240      # partidos recientes que se leen para construir la ventana

FEATURES = {
    "xg": "xG sin penaltis", "xa": "xA", "tiros": "Tiros", "ocasiones": "Ocasiones creadas",
    "toques_area": "Toques en el área", "regates": "Regates", "toques": "Toques",
    "pases_ultimo_tercio": "Pases al último tercio", "pases": "Pases acertados",
    "entradas": "Entradas", "intercepciones": "Intercepciones", "recuperaciones": "Recuperaciones",
    "duelos": "Duelos ganados", "duelos_pct": "% duelos ganados",
    "profundidad": "Altura en el campo", "amplitud": "Amplitud",
}

ROLES = {
    "area": ("Delantero de área", "Vive en el área: muchos tiros y mucho xG, pocos toques fuera de ella.", "#4cc38a"),
    "creador": ("Extremo creador", "Desequilibra y genera: regates, ocasiones creadas y xA muy por encima de la media.", "#5b9bf0"),
    "llegada": ("Interior de llegada", "Juega por delante del balón y pisa área desde segunda línea.", "#7dd3c0"),
    "regateador": ("Regateador vertical", "Conduce y gana duelos hacia delante; menos pase, más uno contra uno.", "#e5a54b"),
    "organizador": ("Organizador", "Mucho balón y mucho pase al último tercio: el equipo pasa por él.", "#b583e6"),
    "recuperador": ("Recuperador", "Entradas, intercepciones y recuperaciones: el que roba.", "#e5616b"),
    "lateral": ("Lateral", "Ocupa la banda en defensa y en ataque; amplitud por encima de todo.", "#f0b8a0"),
    "constructor": ("Central que construye", "Defiende atrás pero inicia el juego: muchísimos pases y toques.", "#8ab4f8"),
    "marca": ("Central de marca", "Duelo, anticipación y despeje; poco protagonismo con el balón.", "#8e9096"),
}


def _features(p: pd.DataFrame) -> pd.DataFrame:
    m = p.minutes / 90
    return pd.DataFrame({
        "xg": p.npxg / m, "xa": p.xa / m, "tiros": p.shots / m, "ocasiones": p.chances / m,
        "toques_area": p.box_touches / m, "regates": p.dribbles / m, "toques": p.touches / m,
        "pases_ultimo_tercio": p.final_third_passes / m, "pases": p.accurate_passes / m,
        "entradas": p.tackles / m, "intercepciones": p.interceptions / m,
        "recuperaciones": p.recoveries / m, "duelos": p.duels_won / m,
        "duelos_pct": (p.duels_won / (p.duels_won + p.duels_lost).replace(0, np.nan)) * 100,
        "profundidad": p.avg_x * 100, "amplitud": (p.avg_y - 0.5).abs() * 200,
    }, index=p.index).fillna(0)


def current_window() -> pd.DataFrame:
    """Últimos WINDOW_MINUTES minutos de cada jugador que ha jugado la temporada en curso con su
    equipo actual (la ventana puede incluir partidos del final de la temporada anterior)."""
    from concurrent.futures import ProcessPoolExecutor

    from futdata.player_seasons import STAT_COLS, _match_rows

    m = pd.read_parquet(PROCESSED / "matches.parquet")
    m["kickoff"] = m["kickoff_utc"].fillna(m["date"].dt.tz_localize("UTC") + pd.Timedelta(hours=15))
    m = m[m.pitchapi_id.notna() & (m.kickoff >= m.kickoff.max() - pd.Timedelta(days=WINDOW_DAYS))]
    jobs = [(r.league, int(r.season), r.pitchapi_id, r.home, r.away) for r in m.itertuples()]
    kick = {(r.league, int(r.season), r.home, r.away): r.kickoff for r in m.itertuples()}
    rows = []
    with ProcessPoolExecutor() as pool:
        for job, chunk in zip(jobs, pool.map(_match_rows, jobs, chunksize=32)):
            for r in chunk:
                r["kickoff"] = kick[(job[0], job[1], job[3], job[4])]
                rows.append(r)
    df = pd.DataFrame(rows).sort_values("kickoff")
    now = int(df.season.max())
    current_team = df[df.season == now].groupby("player_id").last()[["team", "league"]]
    df = df.merge(current_team.reset_index(), on=["player_id", "team", "league"])
    df = df.sort_values("kickoff", ascending=False)
    # Partidos hasta completar la ventana: los anteriores al que la llena quedan fuera
    df["prev_minutes"] = df.groupby("player_id")["minutes"].cumsum() - df["minutes"]
    df = df[df.prev_minutes < WINDOW_MINUTES]
    g = df.groupby("player_id")
    agg = g.agg(name=("name", "first"), photo=("photo", "first"), team=("team", "first"), league=("league", "first"),
                apps=("apps", "sum"), starts=("starts", "sum"), desde=("kickoff", "min"), hasta=("kickoff", "max"),
                this_season=("season", lambda x: int((x == now).sum())),
                **{k: (k, "sum") for k in STAT_COLS})
    w = df.assign(rx=df.rating * df.minutes, rm=df.minutes.where(df.rating.notna())).groupby("player_id")[["rx", "rm"]].sum()
    agg["rating_w"] = (w.rx / w.rm).where(w.rm > 0)
    agg["avg_x"] = g.start_x.mean()
    agg["avg_y"] = g.start_y.mean()
    agg = agg.reset_index()
    agg["season"] = now
    agg["saves"] = agg["saves"].fillna(0)
    return agg[(agg.minutes >= MIN_WINDOW_MINUTES) & agg.avg_x.notna() & (agg.avg_x > 0.15)].reset_index(drop=True)


def _name_roles(c: pd.DataFrame) -> dict[int, str]:
    left = set(c.index)
    names: dict[int, str] = {}

    def take(key, score):
        best = score.loc[sorted(left)].idxmax()
        names[best] = key
        left.discard(best)

    take("area", c.xg + c.toques_area + c.profundidad)
    take("lateral", c.amplitud - c.profundidad)
    take("constructor", c.pases + c.toques - 1.5 * c.profundidad)
    take("marca", c.duelos_pct - c.profundidad - c.ocasiones)
    take("creador", c.xa + c.ocasiones + c.regates)
    take("recuperador", c.entradas + c.recuperaciones + c.intercepciones)
    take("organizador", c.pases_ultimo_tercio + c.pases)
    take("regateador", c.regates + c.duelos)
    for i in left:
        names[i] = "llegada"
    return names


def build() -> pd.DataFrame:
    raw = pd.read_parquet(PROCESSED / "player_seasons.parquet")
    p = raw[(raw.minutes >= MIN_MINUTES) & (raw.role != "POR") & raw.avg_x.notna()].reset_index(drop=True)
    X = _features(p)
    keys = list(FEATURES)
    scaler = StandardScaler().fit(X[keys])
    Z = scaler.transform(X[keys])
    pca = PCA(n_components=2, random_state=0).fit(Z)
    pcs = pca.transform(Z)
    sign = np.sign(pca.components_[0][keys.index("xg")]) or 1  # eje 1 crece hacia el ataque
    sign2 = np.sign(pca.components_[1][keys.index("xa")]) or 1  # eje 2 crece con la creación
    km = KMeans(N_ROLES, n_init=40, random_state=0).fit(Z)
    names = _name_roles(pd.DataFrame(km.cluster_centers_, columns=keys))

    out = p[["player_id", "name", "photo", "team", "league", "season", "minutes", "apps", "starts",
             "goals", "assists", "xg", "xa", "rating_w"]].copy()
    out["pc1"], out["pc2"] = pcs[:, 0] * sign, pcs[:, 1] * sign2
    out["role"] = [names[i] for i in km.labels_]
    for k in keys:
        out[f"v_{k}"] = X[k].values
        out[f"z_{k}"] = Z[:, keys.index(k)]
        # percentil dentro de su rol (0–100)
    for k in keys:
        out[f"p_{k}"] = out.groupby("role")[f"v_{k}"].rank(pct=True) * 100
    out["window"] = "season"

    # Estado actual: mismos escalado, PCA y roles
    cur = current_window()
    Xc = _features(cur)
    Zc = scaler.transform(Xc[keys])
    pc_cur = pca.transform(Zc)
    now = cur[["player_id", "name", "photo", "team", "league", "season", "minutes", "apps", "starts",
               "goals", "assists", "xg", "xa", "rating_w"]].copy()
    now["pc1"], now["pc2"] = pc_cur[:, 0] * sign, pc_cur[:, 1] * sign2
    now["role"] = [names[i] for i in km.predict(Zc)]
    for k in keys:
        now[f"v_{k}"] = Xc[k].values
        now[f"z_{k}"] = Zc[:, keys.index(k)]
    for k in keys:  # percentil frente a las temporadas completas del mismo rol
        ref = {r: np.sort(g[f"v_{k}"].to_numpy()) for r, g in out.groupby("role")}
        now[f"p_{k}"] = [np.searchsorted(ref[r], v, side="right") / max(len(ref[r]), 1) * 100
                         for r, v in zip(now.role, now[f"v_{k}"])]
    now["window"] = "now"
    now["window_from"] = cur.desde.astype(str)
    now["window_to"] = cur.hasta.astype(str)
    now["this_season"] = cur.this_season
    now["short_sample"] = cur.minutes < WINDOW_MINUTES
    out = pd.concat([out, now], ignore_index=True)
    out.to_parquet(PROCESSED / "player_styles.parquet", index=False)

    roles = []
    for i in range(N_ROLES):
        key = names[i]
        cz = pd.Series(km.cluster_centers_[i], index=keys)
        members = out[out.role == key]
        roles.append({"key": key, "name": ROLES[key][0], "description": ROLES[key][1], "color": ROLES[key][2],
                      "size": int(len(members)), "pc": [float(members.pc1.mean()), float(members.pc2.mean())],
                      "centroid": {k: float(v) for k, v in cz.items()},
                      "traits_high": [FEATURES[k] for k in cz.sort_values(ascending=False).index[:3]]})
    meta = {"min_minutes": MIN_MINUTES, "n": int(len(out)),
            "explained": [float(v) for v in pca.explained_variance_ratio_],
            "features": [{"key": k, "label": v} for k, v in FEATURES.items()],
            "axes": [{"name": "Más cerca del gol", "loadings": dict(zip(keys, map(float, pca.components_[0] * sign)))},
                     {"name": "Más creación", "loadings": dict(zip(keys, map(float, pca.components_[1] * sign2)))}],
            "roles": roles}
    (PROCESSED / "player_roles.json").write_text(json.dumps(meta, ensure_ascii=False))
    log.info("player_styles: %d jugadores-temporada, %d roles", len(out), N_ROLES)
    return out


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    o = build()
    cur = o[o.window == "now"]
    print(f"Estado actual: {len(cur)} jugadores (muestra corta: {int(cur.short_sample.sum())})")
    for key, g in o[(o.season == 2025) & (o.window == "season")].groupby("role"):
        print(f"{ROLES[key][0]:24s} {len(g):4d}  {g.sort_values('minutes', ascending=False).name.head(5).tolist()}")
