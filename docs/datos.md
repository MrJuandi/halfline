# Inventario de datos

Alcance: LaLiga (SP1), Premier League (E0), Serie A (I1), Bundesliga (D1) y Ligue 1 (F1), temporadas 2021/22 a la actual.
Polymarket queda fuera del primer alcance.

Todo lo descargado se guarda sin transformar en `data/raw/<fuente>/` y cada petición queda registrada en `data/raw/_manifest.jsonl`.
Descarga: `python -m futdata download`. Estado y última fecha disponible: `python -m futdata status`.

## 1. Fuentes con cobertura continua (se descargan)

| Fuente | Datos | Nivel | Temporadas | Actualización |
|---|---|---|---|---|
| Football-Data.co.uk | Resultado y descanso; tiros, tiros a puerta, córners, faltas, tarjetas; árbitro (solo Premier); cuotas 1X2 pre-cierre y cierre, más/menos 2,5, hándicap asiático; próximos partidos con cuotas (`fixtures.csv`) | partido | 2021/22 → hoy | Varias veces por semana |
| ESPN (API no oficial) | Posesión, pases y precisión, centros, balones largos, entradas, intercepciones, despejes, paradas, fueras de juego, tiros bloqueados; alineaciones, formación, titulares y suplentes; estadísticas básicas por jugador; eventos con minuto (goles, tarjetas, cambios); narración | partido, jugador, evento | 2021/22 → hoy | Tras cada partido |
| PitchAPI (clave gratuita en `.env`) | Tiros con coordenadas, **xG**, xGOT, situación y tipo; estadísticas de equipo (xG, xG sin penaltis, grandes ocasiones, duelos, regates, toques en el área…); estadísticas por jugador (nota, duelos, recuperaciones, xA…); alineaciones, eventos, momentum. Desde 2024/25 (Premier desde 2021/22): **mapas de calor**, xT, VAEP, redes de pase | partido, jugador, tiro | 2021/22 → hoy | Tras cada partido. Sin términos de uso publicados; proveedor original no declarado |
| Transfermarkt (dataset dcaribou) | Valores de mercado con fecha, jugadores, clubes, traspasos, apariciones, alineaciones | jugador, club | ~2012 → 6/7/2026 | **Congelado** a 6/7/2026 |

Avisos de la propia Football-Data:
- Cuotas pre-cierre capturadas el viernes antes de las 17:00 (hora británica) para el fin de semana y el martes antes de las 13:00 para entre semana. Cuotas de cierre solo desde 2019/20 (Pinnacle desde 2012/13).
- Desde el 23/07/2025 las cuotas de Pinnacle están desfasadas y no se usan en la media ni el máximo. No usar Pinnacle desde 2025/26.


## 2. Datos interesantes que no tenemos y dónde conseguirlos

| Dato | Para qué | Mejor opción encontrada | Coste y condiciones | Cobertura | Decisión propuesta |
|---|---|---|---|---|---|
| Mapas de calor por jugador y equipo | Posición y zonas de actuación, estilo | **PitchAPI** (`/v1/matches/{id}/heatmaps`, rejilla 16×12) | Gratis con clave API, sin límite de peticiones anunciado. Servicio de una sola persona, sin SLA. Los identificadores de liga coinciden con los de FotMob, así que probablemente reempaqueta datos de terceros: revisar sus términos | 2021 → hoy | Probar. Requiere que el usuario se registre para obtener la clave |
| Eventos completos con coordenadas (pases, conducciones, presiones) | xT, VAEP, redes de pases | PitchAPI (eventos, red de pases, 88 métricas avanzadas) | PitchAPI gratis | PitchAPI 2021 → hoy | PitchAPI para 2021+ |
| Estadísticas avanzadas por jugador (duelos, regates, pases progresivos, nota) | Calidad individual | PitchAPI; API-Football | API-Football: 100 peticiones al día gratis, temporadas antiguas limitadas | PitchAPI 2021 → hoy | Probar PitchAPI |
| xGOT (xG tras el tiro) | Rendimiento de porteros | PitchAPI | Gratis | 2021 → hoy | Con lo anterior |
| Lesiones y sanciones | Bajas antes del partido | API-Football (`/injuries`); FPL (solo Premier, estado actual con fecha de la noticia) | API-Football con clave; FPL gratis | Histórico no verificado en API-Football; FPL solo temporada en curso | Empezar a guardar FPL ya; probar API-Football |
| Valor de mercado actualizado | Fuerza de plantilla | `transfermarkt-api` (código abierto, se ejecuta en local y lee Transfermarkt) | Gratis; scraping de Transfermarkt, revisar condiciones | Actual | Para cubrir desde 7/2026 |
| Alineaciones probables antes del partido | Modelo a T−1 h | PitchAPI (alineaciones confirmadas o previstas) | Gratis | Solo prospectivo | Guardar de forma prospectiva |
| Partidos europeos (Champions, Europa League) | Fatiga y rotaciones | ESPN (`uefa.champions`, `uefa.europa`) | Gratis | 2021 → hoy | Añadir al descargador de ESPN |
| Meteorología | Contexto | Open-Meteo Historical | Gratis para uso no comercial | 1940 → hoy (comprobado) | Opcional |
| Entrenadores y cambios de entrenador | Contexto | Transfermarkt vía `transfermarkt-api`; Wikipedia | Gratis | Histórico | Opcional |
| Asistencia de público | Contexto (temporada sin público 2020/21) | ESPN (`gameInfo`) | Gratis | Por comprobar | Ya viene en los resúmenes de ESPN si existe |
| Tracking (posiciones de los 22 jugadores) | Análisis espacial avanzado | Solo de pago (StatsBomb 360, SkillCorner, Second Spectrum) | Licencia | — | Fuera de alcance salvo licencia de la universidad |
| Paquete profesional completo (Opta, StatsBomb, Wyscout, Sportmonks) | Todo lo anterior con licencia clara | Proveedores comerciales; TheStatsAPI desde 50 $/mes con prueba de 7 días | De pago | Hasta 10 años | Preguntar a la universidad |

Descartadas: Understat (sitio caído desde el 13/10/2026; sustituido por PitchAPI); StatsBomb Open Data (sin cobertura continua: últimos partidos de las 5 ligas en mayo de 2024); Sofascore, FotMob y WhoScored (403 al acceso automatizado y condiciones que prohíben el scraping); FBref (perdió los datos avanzados de Opta el 20/01/2026; solo conserva estadísticas básicas).

## 3. Fuentes consultadas

- [PitchAPI](https://pitchapi.dev/) y [reseña en sportsapis.dev](https://sportsapis.dev/apis/pitchapi)
- [TheStatsAPI: histórico y precios](https://thestatsapi.com/blog/how-to-get-historical-football-data-api); [mapas de calor por jugador](https://www.thestatsapi.com/docs/api-reference/matches/player-heatmap.md)
- [FBref pierde los datos de Opta (Awful Announcing)](https://awfulannouncing.com/soccer/sports-reference-pulls-advanced-data-agreement-violation-dispute.html)
- [API-Football: notas de conexión](https://getbruin.com/docs/ingestr/soccer-sources/api-football.html)
- [Hudl StatsBomb: datos gratis Euro 2025](https://www.hudl.com/blog/hudl-statsbomb-free-euro-2025-data)
- [Rastreador de lesiones de Flashscore (Apify)](https://apify.com/harry.automazione/flashscore-injuries-suspensions)
- [transfermarkt-datasets (dcaribou)](https://github.com/dcaribou/transfermarkt-datasets), [transfermarkt-api](https://github.com/felipeall/transfermarkt-api)
- [Open-Meteo Historical Weather API](https://open-meteo.com/en/docs/historical-weather-api)

## 4. Huecos conocidos

- ESPN no tiene datos de 5 partidos de LaLiga 2022/23 (Almería–Betis, Sevilla–Mallorca y Valencia–Athletic del 11/02/2023; Espanyol–Real Sociedad del 13/02/2023; Real Madrid–Elche del 15/02/2023): figuran como programados, sin marcador ni estadísticas. Están en Football-Data y PitchAPI.
- Nantes–Toulouse (Ligue 1, 17/05/2026) fue abandonado y no tiene resumen en ESPN.

## 5. Tabla maestra de partidos

`python -m futdata.matches` genera:
- `data/processed/matches.parquet`: un partido por fila (referencia: Football-Data) con `match_id`, liga, temporada, fecha, hora UTC, equipos con nombre canónico, marcador y los identificadores `espn_id` y `pitchapi_id`.
- `data/processed/team_names.csv`: diccionario de nombres de equipo por fuente y liga, con los votos que lo respaldan.

Los nombres de ESPN y PitchAPI se aprenden de los propios partidos: los que coinciden en fecha (±1 día) y marcador con uno de Football-Data votan por el emparejamiento. 138 equipos, sin conflictos.

Resultado (14/10/2026): 9.205 partidos; 9.199 con ESPN y 9.203 con PitchAPI; 0 marcadores distintos entre fuentes. Sin unir: los 5 partidos de LaLiga de febrero de 2023 sin datos en ESPN, Mallorca–Girona (03/03/2024) y Union Berlin–Bochum (14/12/2024) ausentes en PitchAPI, Nantes–Toulouse abandonado (sin ESPN), y el desempate por el descenso Spezia–Verona (11/06/2023), que Football-Data no incluye.

## 6. Estadísticas por equipo y partido

`python -m futdata.team_stats` genera `data/processed/team_match_stats.parquet`: una fila por equipo y partido (18.410 filas) con `match_id`, lado (local o visitante), equipo, rival, goles a favor y en contra, y las estadísticas de cada fuente con prefijo:

| Prefijo | Fuente | Columnas | Cobertura |
|---|---|---|---|
| `fd_` | Football-Data | 7 (tiros, a puerta, córners, faltas, tarjetas, goles al descanso) | 100 % |
| `espn_` | ESPN | 28 (posesión, pases, centros, balones largos, entradas, intercepciones, despejes, paradas…) | 96,3 % |
| `pa_` | PitchAPI | 43 (xG, xG sin penaltis, en jugada, a balón parado, a puerta; grandes ocasiones, duelos, regates, toques en el área…) | 100 % |
| `adv_` | PitchAPI avanzada | 64 (xT, VAEP, pases y conducciones progresivas, PPDA, field tilt, recuperaciones altas…) | 53,5 % (Premier desde 2021/22; resto desde 2024/25) |

Son estadísticas del propio partido: solo sirven para construir variables con partidos anteriores.

Comprobaciones: las tres fuentes coinciden exactamente en el 87–99 % de los casos para tiros, tiros a puerta, córners, tarjetas y faltas, con medias casi iguales. xG medio 1,39 por equipo frente a 1,41 goles (correlación 0,60).

Limpieza: ESPN pone ceros en los equipos de los que no tiene estadísticas (posesión 0 %, 0 pases, 0 tiros). Se tratan como datos que faltan: 677 filas (329 partidos completos y 19 equipos sueltos, sobre todo de 2021 a 2023). Si la posesión de ESPN no suma 100, se anula.

## 7. Variables pre-partido

`python -m futdata.features` genera `data/processed/features.parquet`: un partido por fila (9.205) con el resultado (`result` H/D/A y goles) y 223 columnas calculadas **solo con información anterior al inicio**:

- Forma de cada equipo (`home_` / `away_`): media de los últimos 5 y 10 partidos (`r5_`, `r10_`) y media exponencial con semivida de 5 partidos (`ewm_`) de goles, xG, xG sin penaltis, xG a puerta, tiros, tiros a puerta, grandes ocasiones, toques en el área, córners y precisión de pase, a favor (`_for`) y en contra (`_against`); más posesión y puntos. La forma cruza temporadas.
- `elo` (K=20, ventaja local 60, 1.500 al aparecer; peso extra a goleadas), `rest_days` (solo liga) y `n_prev`.
- Diferencias local − visitante (`diff_*`, `elo_diff`).
- Mercado: `mkt_p_*` (cuotas medias pre-cierre sin margen con el método de potencia, válidas para predecir), `mkt_odds_*` (esas cuotas tal cual), `mkt_overround` (su margen) y `close_p_*` (cierre, solo referencia).

Fuga temporal: tests automáticos (`tests/test_features.py`) comprueban que el partido que se predice no entra en sus propias medias, que cambiar su resultado no altera sus variables y que el Elo solo usa resultados previos. Comprobado además con los datos reales: recalcular sin los partidos posteriores a 2024 deja idénticas todas las variables anteriores.

2021/22 es la temporada de calentamiento: los equipos aún no tienen historial completo.

Prueba rápida (regresión logística; entrenamiento 2022/23–2024/25, test 2025/26–2026/27, 2.049 partidos), log-loss: frecuencias 1,071 · Elo 0,995 · Elo + forma xG 0,994 · Elo + forma completa 0,991 · mercado pre-cierre 0,977.

## 8. Datos fabricados: estilos de juego y perfiles de jugador

Para regenerar todo: `python -m futdata.player_seasons && python -m futdata.crests && python -m futdata.styles && python -m futdata.player_styles`.

- **Estilos de equipo** (`futdata/styles.py` → `data/processed/styles.json`): 19 métricas por equipo y temporada (mínimo 8 partidos), estandarizadas sobre todas las ligas y temporadas. PCA: el eje 1 («Dominio del partido», 48 % de la varianza) y el eje 2 («Juego por fuera y físico», 12 %) explican el 60 %. K-means con 6 arquetipos nombrados por reglas sobre los centroides: Dominio total, Control y llegada, Presión y orden, Juego directo, Físicos de área y Bloque que sufre. Incluye los equipos más parecidos de cada temporada, los mayores cambios entre temporadas (Newcastle 21→22, Leverkusen 22→23, Stuttgart 22→23, Tottenham 22→23…) y la posición media de cada liga.
- **Jugador-temporada** (`futdata/player_seasons.py` → `data/processed/player_seasons.parquet`): 16.534 filas con minutos, goles, xG, xA, regates, acciones defensivas, nota media y posición media de salida.
- **Perfiles de jugador** (`futdata/player_styles.py` → `player_styles.parquet`, `player_roles.json`): jugadores de campo con al menos 900 minutos (7.408 jugador-temporadas), 16 rasgos por 90 minutos más profundidad y amplitud. PCA para el mapa y k-means con 9 roles: Delantero de área, Extremo creador, Interior de llegada, Regateador vertical, Organizador, Recuperador, Lateral, Central que construye y Central de marca. Percentiles dentro del rol y jugadores parecidos por distancia euclídea en el espacio estandarizado.
- **Escudos y colores** (`futdata/crests.py`): los 138 escudos se guardan en `data/raw/crests/` y se sirven desde la API; el color de cada club es el dominante del escudo, con excepciones manuales cuando el escudo engaña (Barcelona, Real Madrid, Juventus…).

Limitaciones: los arquetipos y roles son descriptivos y dependen de las métricas elegidas; k-means asume grupos compactos, así que hay equipos y jugadores a caballo entre dos grupos. El impacto on/off y los parecidos no son causales.

### Estado actual (ventana móvil)

La temporada en curso no entra como temporada en los estilos (está incompleta). En su lugar:
- **Equipos:** últimos 10 partidos de liga de cada equipo que juega la temporada en curso (pueden incluir el final de la anterior; mínimo 5, con aviso si son menos de 10). Se proyectan con el mismo escalado, PCA y arquetipos y se comparan con cómo acabó la temporada anterior.
- **Jugadores:** últimos 900 minutos con su equipo actual (mínimo 450, marcado como muestra corta). Mismos escalado, PCA y roles; los percentiles se calculan frente a las temporadas completas de su rol y los parecidos se buscan entre temporadas completas.
