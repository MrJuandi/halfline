# Modelos: estado del arte y plan con nuestros datos

Fecha: 14/10/2026. Complementa `docs/datos.md`.

## 0. Punto de partida

Conjunto de test: 2025/26 y 2026/27 (2.049 partidos), entrenamiento 2022/23–2024/25. Log-loss 1X2:

| Modelo | Log-loss |
|---|---|
| Frecuencias | 1,071 |
| Regresión logística: Elo | 0,995 |
| Elo + forma completa | 0,991 |
| Mercado pre-cierre (media, sin margen) | 0,977 |
| Mercado pre-cierre recalibrado (logística sobre sus log-odds) | 0,976 |
| **Mercado pre-cierre + Elo + xG** | **0,978** |
| Mercado de cierre | 0,976 |

Lectura:
- Nuestras variables actuales no añaden nada al mercado: al juntarlas empeora un poco (sobreajuste). Es lo esperable; el mercado ya descuenta Elo y xG.
- Pre-cierre frente a cierre: 0,001 de diferencia, con error estándar emparejado de 0,0014. Con 2.000 partidos, **diferencias de log-loss menores de ~0,003–0,005 entre modelo y mercado son ruido**. Hay que evaluar con intervalos, no con la cifra suelta.
- La distancia a cubrir como modelo independiente es 0,991 → ~0,977. Llegar ahí ya es un buen resultado académico; superarlo de forma sostenida es raro en la literatura.

Conclusión de diseño: el objetivo no es "ganar al mercado en 1X2 con más variables", sino (a) un modelo independiente bien calibrado que se acerque al mercado, (b) buscar ventaja donde el mercado pre-cierre tiene menos información (alineaciones, nichos) y (c) medirlo con la línea de cierre.

## 1. Estado del arte

### 1.1 Modelos de goles (la base de casi todo)

| Familia | Idea | Referencia | Comentario |
|---|---|---|---|
| Poisson independiente | goles ~ Poisson(ataque × defensa rival × ventaja local) | Maher (1982) | Línea base clásica |
| Dixon-Coles | Poisson + corrección de marcadores bajos (ρ) + **decaimiento temporal** de los partidos (ξ) | Dixon y Coles (1997) | Sigue siendo la referencia práctica. Da la distribución de marcadores completa |
| Poisson bivariante / inflado en empates | Correlación entre goles de ambos equipos | Karlis y Ntzoufras (2003) | Mejora los empates, que es donde fallan los Poisson |
| Conteos más flexibles | Binomial negativa, Weibull-count | Boshnakov, Kharrat y McHale (2017) | Mejor dispersión; ganancia pequeña |
| Dinámicos (espacio de estados) | Fuerzas de ataque y defensa que evolucionan como paseo aleatorio, filtrado tipo Kalman o bayesiano | Rue y Salvesen (2000); Koopman y Lit (2015) | Sustituye el decaimiento ad hoc por un modelo de evolución. Estado del arte en modelos estadísticos |
| Jerárquicos bayesianos | Fuerzas con prior común por liga, contracción para equipos con poca muestra | Baio y Blangiardo (2010) | Útil para ascendidos y principio de temporada |
| Basados en xG | Ajustar el modelo de goles a xG (o mezcla goles/xG) en vez de a goles | práctica estándar (SPI de FiveThirtyEight usaba goles ajustados + xG de tiros + xG sin tiro) | xG es menos ruidoso que los goles: estima la fuerza con menos partidos |

Ventaja clave para nosotros: **un modelo de goles da a la vez 1X2, más/menos 2,5 y hándicap asiático**, y tenemos cuotas de los tres mercados.

### 1.2 Ratings

- **Elo con margen de goles** (World Football Elo, ClubElo). El nuestro: K=20, ventaja local 60, sin ajustar.
- **pi-ratings** (Constantinou y Fenton, 2013): rating separado en casa y fuera, actualizado por error en goles con rendimientos decrecientes. En el Soccer Prediction Challenge 2017 (Berrar, Lopes y Dubitzky, 2019) los mejores combinaban ratings tipo pi/Berrar con árboles potenciados.
- **Ratings sobre xG**: el mismo Elo/pi actualizado con xG en lugar de goles.

### 1.3 Aprendizaje automático

- **Árboles potenciados (CatBoost, LightGBM) sobre variables de rating y forma**: lo que mejor funciona en tabulares de este tamaño. Ganan poco frente a una buena logística ordinal si las variables ya son buenas.
- **Regresión ordinal / multinomial con calibración posterior** (temperatura o calibración de Dirichlet): difícil de batir con ~9.000 partidos.
- **Redes neuronales** sobre tabulares de partido: no aportan con este tamaño de muestra. Donde sí son estado del arte es con secuencias de eventos o tracking (modelos tipo transformer para valorar acciones, TacticAI de DeepMind y Liverpool), que no son de predicción de resultado prepartido.
- **Decorrelación con el mercado** (Hubáček, Šourek y Železný, 2019): entrenar penalizando la correlación con las probabilidades de la casa, porque un modelo que replica al mercado no tiene ventaja aunque tenga mejor log-loss. Es la línea más directamente relevante para "ML frente a mercados".

### 1.4 Modelos con jugadores

- **Ratings de jugador tipo plus-minus ajustado (RAPM)**: regresión ridge sobre tramos de partido sin cambios, con goles o xG a favor y en contra por 90 minutos como objetivo. Arntzen y Hvattum (2021) muestran que combinar ratings de equipo y de jugador mejora la predicción.
- **Valor de mercado de Transfermarkt** como medida de calidad de plantilla: predice resultados internacionales al nivel de las casas (Peeters, 2018). El valor del **once titular** es un indicador fuerte y barato.
- Lo importante no es el rating en sí, sino que permite **reaccionar a la alineación**: bajas, rotaciones, porteros suplentes.

### 1.5 Mercados

- La **cuota de cierre** es el mejor predictor disponible; la literatura de eficiencia (y nuestra propia tabla) lo confirma.
- Sesgos documentados: favorito-*longshot*, infravaloración del empate en algunas ligas, sobrerreacción a resultados recientes. Son pequeños y muchos desaparecen al quitar el margen bien.
- **Quitar el margen**: proporcional, método de Shin (Štrumbelj, 2014), *power* (potencia) y aditivo. Shin y potencia corrigen el sesgo favorito-*longshot* y suelen calibrar mejor. Desde el 15/10/2026 usamos potencia (sección 8).
- **CLV (closing line value)**: si nuestras apuestas simuladas consiguen sistemáticamente mejor cuota que el cierre, hay información real. Es la métrica de validación preferida porque converge mucho más rápido que el ROI.
- **Tamaño de apuesta**: Kelly fraccionado, con contracción por incertidumbre del modelo (Baker y McHale, 2013).

### 1.6 Evaluación

- **RPS** (Constantinou y Fenton, 2012) para 1X2 por ser ordinal, más log-loss (Wheatcroft defiende la *ignorance score* / log-loss frente al RPS) y Brier.
- Validación **hacia delante por jornadas** (*walk-forward*), nunca aleatoria.
- Comparación emparejada modelo–mercado con *bootstrap* por partido o test de Diebold-Mariano.
- Diagramas de fiabilidad (ya previstos en la página Modelo).

## 2. Qué podemos hacer con nuestros datos

| Dato que tenemos | Qué habilita |
|---|---|
| Goles y xG/npxG/xGOT por partido (PitchAPI, 100 %) | Modelos de goles y ratings sobre xG |
| Cuotas 1X2, más/menos 2,5 y hándicap asiático, pre-cierre y cierre, varias casas y Betfair Exchange | Comparar en tres mercados; CLV; movimiento de línea; sesgos |
| Tiros con coordenadas (PitchAPI) | xG propio (control de calidad del xG del proveedor); simulación por tiros |
| Alineaciones, cambios con minuto (ESPN, PitchAPI) | Tramos de partido → RAPM; minutos; rotaciones |
| Estadísticas por jugador (nota, xA, duelos…) | Ratings de jugador, valor del once |
| Transfermarkt (valores con fecha, hasta 6/7/2026) | Valor del once titular y de la plantilla; fichajes |
| Eventos y momentum por minuto | Probabilidad de victoria en directo |
| Estilos y roles (ya calculados) | Interacciones de estilo (p. ej. presión contra salida en corto); análisis más que predicción |

## 3. Plan propuesto (por prioridad)

### Fase 1 — Banco de evaluación (imprescindible antes de cualquier modelo)
- `futdata/models/eval.py`: *walk-forward* por jornada, re-entrenando hasta la víspera; métricas RPS, log-loss, Brier; calibración; *bootstrap* emparejado frente a mercado pre-cierre y cierre; desglose por liga, temporada y tramo de temporada.
- Mercados 1X2, más/menos 2,5 y hándicap asiático desde el principio.
- ~~Quitar el margen con Shin además del proporcional.~~ Hecho: potencia como referencia (sección 8).

### Fase 2 — Modelos de goles
1. Dixon-Coles con decaimiento temporal, por liga, ajustado a **goles**, a **npxG** y a una **mezcla** (peso a estimar). Penaltis aparte.
2. Poisson bivariante / inflado en empates.
3. Modelo dinámico bayesiano (fuerzas como paseo aleatorio, observaciones de goles y xG, prior jerárquico por liga). Con PyTorch o `scipy` se puede hacer un filtrado aproximado sin dependencias nuevas; con PyMC/NumPyro sería más cómodo.

Esperable: 1X2 en torno a 0,980–0,985 y, sobre todo, probabilidades coherentes para los tres mercados.

### Fase 3 — Ratings y meta-modelo
- Ajustar el Elo (K, ventaja local, margen) por máxima verosimilitud; añadir pi-ratings y Elo sobre xG.
- Meta-modelo: logística ordinal y CatBoost/LightGBM sobre salidas de los modelos de goles + ratings + descanso + forma; calibración final.
- Probar el término de **decorrelación con el mercado**.

### Fase 4 — Alineaciones (donde más ventaja esperamos)
Las cuotas pre-cierre se capturan el viernes o el martes, antes de conocer las alineaciones; el cierre ya las incluye.
- RAPM de jugadores con tramos de ESPN/PitchAPI y xG como objetivo, con contracción hacia el valor de mercado o la nota.
- Fuerza del once = suma de ratings de titulares; diferencia frente al once "habitual".
- Pregunta de investigación concreta: **¿cuánto del movimiento pre-cierre → cierre explica la alineación?** Con datos históricos se responde ya (las alineaciones reales sirven como proxy de las confirmadas a T−1 h).
- Para usarlo en real hay que guardar alineaciones confirmadas y cuotas a T−1 h de forma prospectiva (pendiente en `docs/datos.md`).

### Fase 5 — Mercado como objeto de estudio
- Modelo del movimiento de línea (pre-cierre → cierre) y CLV de nuestras señales.
- Sesgos: favorito-*longshot*, empate, ascendidos, primeras jornadas, tras partido europeo (requiere añadir Champions y Europa League de ESPN).
- Comparar media de casas, Bet365 y Betfair Exchange (la bolsa suele estar mejor calibrada). Pinnacle descartado desde 2025/26.

### Fase 6 — Producto (web)
- **Simulación de temporada** (Monte Carlo con el modelo de goles): probabilidades de título, Europa y descenso para la página de liga.
- **Probabilidad de victoria en directo** a partir del modelo prepartido + minuto + marcador + rojas (+ momentum): curva en la ficha de partido.
- xG propio a partir de tiros: más como validación del proveedor que como mejora predictiva.

## 4. Qué no hacer

- Validación cruzada aleatoria (fuga temporal) o usar `close_p_*` como variable.
- Redes profundas sobre 9.000 filas, o cientos de variables de forma redundantes (ya vemos que empeoran).
- Medir por porcentaje de aciertos.
- Simular ROI con la cuota **máxima** del mercado (sesgo de selección) o sin intervalos: con 2.000 partidos el ROI es casi todo ruido. Primero CLV.
- Mezclar Pinnacle de 2025/26 en adelante.

## 5. Dependencias

Instalado: scikit-learn, scipy, statsmodels, PyTorch. Recomendado añadir `lightgbm` o `catboost`; opcional `pymc` o `numpyro` para la fase bayesiana y `penaltyblog` como referencia de Dixon-Coles, pi-ratings y quitar márgenes (útil para contrastar nuestra implementación).

## 6. Resultados de la primera ronda (14/10/2026)

> Cifras con el margen quitado por el método proporcional. Con el método de potencia (actual), ver sección 8: los modelos no cambian y el mercado mejora ~0,001.

Código: `futdata/models/` (`data.py`, `goals.py`, `ratings.py`, `lineups.py`, `evaluate.py`). Tests: `tests/test_models.py`.
Ejecutar: `python -m futdata.models.evaluate` (~6 min) → `data/processed/model_predictions.parquet` y `model_report.json`.

Protocolo: hiperparámetros elegidos en 2024/25 (validación); test en 2025/26 y 2026/27 (2.049 partidos), evaluado una sola vez. Modelos de goles re-ajustados cada semana; capa de probabilidad entrenada con las temporadas anteriores. "vs mercado" = log-loss del modelo − log-loss del mercado pre-cierre (positivo = peor), con IC bootstrap al 95 %.

| Modelo | Validación 2024/25 | vs mercado | Test 2025–26 | vs mercado [IC 95 %] |
|---|---|---|---|---|
| Mercado pre-cierre | 0,964 | — | 0,977 | — |
| Mercado cierre | 0,961 | −0,003 | 0,976 | −0,001 [−0,004; +0,002] |
| Elo actual (`features.py`) | 0,989 | +0,025 | 0,995 | +0,018 [+0,011; +0,027] |
| Dixon-Coles con goles | 0,984 | +0,020 | 0,996 | +0,019 [+0,012; +0,028] |
| Dixon-Coles 75 % xG + 25 % goles | 0,975 | +0,011 | 0,995 | +0,019 [+0,012; +0,025] |
| **Elo ajustado con xG** | 0,972 | +0,008 | **0,993** | **+0,016** [+0,008; +0,023] |
| Pi-ratings con xG | 0,972 | +0,008 | 0,998 | +0,021 [+0,012; +0,030] |
| Meta-modelo logístico | 0,977 | +0,013 | 0,995 | +0,018 [+0,010; +0,027] |
| Meta-modelo de árboles | 0,987 | +0,023 | 1,003 | +0,026 [+0,015; +0,036] |
| Mercado + Dixon-Coles | 0,964 | −0,000 | 0,977 | −0,000 [−0,003; +0,003] |
| Mercado + meta-modelo | 0,966 | +0,002 | 0,979 | +0,002 [−0,003; +0,006] |

Elegidos en validación: Dixon-Coles con objetivo 25 % goles + 75 % xG, semivida 180 días, ρ = −0,10; Elo K=20, ventaja local 40, ascendidos empiezan en 1.400, resultado sustituido por los puntos esperados según el xG; pi-ratings λ=0,1, γ=0,5 con diferencia de xG.

Más/menos 2,5 (test): mercado 0,671; Dixon-Coles xG 0,680.

Once titular (Transfermarkt, solo 2025/26): añadirlo a Dixon-Coles mejora 0,001; añadirlo al mercado no aporta (+0,0005 [−0,003; +0,004]). Pero el valor relativo del once explica el 10 % del movimiento de la cuota entre pre-cierre y cierre (correlación 0,32): el mercado ya lo incorpora al cierre, y el margen total entre pre-cierre y cierre es solo ~0,001–0,003.

Apuestas simuladas (test, ventaja > 3 pp, cuota media pre-cierre): ROI negativo en todos los modelos (−6 % a −19 %), CLV indistinguible de cero.

Conclusiones:
- Ningún modelo mejora al mercado ni le añade información. Todos los intervalos de "mercado + modelo" incluyen el cero.
- Lo que sí mejora frente a lo que teníamos: usar xG dentro de los ratings y empezar a los ascendidos más abajo (Elo 0,995 → 0,993 en test; 0,989 → 0,972 en validación).
- El test fue más difícil que la validación para los modelos (2025/26: +0,016 a +0,022 frente al mercado). El hueco es mayor en el primer 20 % de cada temporada (Dixon-Coles +0,030 frente a +0,015 en el resto): ahí el mercado sabe de fichajes y pretemporada y nosotros no.
- Los árboles y meta-modelos con muchas variables empeoran: con ~5.000 partidos de entrenamiento, menos es más.

## 7. Contra Polymarket (14/10/2026)

> Cifras con el método proporcional; con potencia, ver sección 8.

Datos: `python -m futdata.polymarket` (descarga y genera `data/processed/polymarket.parquet`), comparación con `python -m futdata.models.vs_polymarket` → `data/processed/polymarket_report.json`.
2.005 partidos de las 5 ligas desde agosto de 2025 (los 3 mercados sí/no del 1X2), precio horario. Volumen mediano por partido: ~570.000 $. 656 partidos con comisiones activadas.

Precisión (log-loss), en el momento de la captura pre-cierre de Football-Data (n = 1.883):

| Fuente | Log-loss | vs Polymarket [IC 95 %] |
|---|---|---|
| Polymarket | 0,9769 | — |
| Casas (media) | 0,9770 | +0,0001 [−0,0014; +0,0015] |
| Betfair Exchange | 0,9764 | −0,0005 [−0,0013; +0,0003] |
| Modelo Elo xG | 0,9928 | +0,016 [+0,008; +0,024] |
| Dixon-Coles xG | 0,9956 | +0,019 |
| Meta-modelo | 0,9954 | +0,019 |

Al cierre (n = 1.845): Polymarket 0,9759; casas 0,9764; Betfair 0,9755.

Estrategias (comprar el "Sí" cuando la referencia da más probabilidad que el precio de Polymarket):
- Con casas o Betfair como referencia, las diferencias de más de 2 pp casi no existen: 6–75 apuestas en 14 meses según el momento y el coste supuesto; resultados sin significación.
- Con nuestros modelos: 500–1.600 apuestas, ROI entre −1 % y −9 %, ningún intervalo por encima de cero.

Conclusión: Polymarket en estas ligas es tan preciso como las casas y Betfair; su precio sigue al mercado de apuestas casi al punto. Nuestros modelos son ~0,016 peores. No hay ventaja ni con modelo ni copiando a las casas, al menos con precios horarios.

## 8. Referencia del mercado con el método de potencia (15/10/2026)

Motivo (`docs/sesgos_mercado.md`): el método proporcional deja un sesgo favorito-longshot (pendiente de
calibración 1,08–1,10 en todos los periodos); el de potencia lo deja en 1,01–1,02.

Código: `futdata/models/margin.py` (`proportional`, `shin`, `power` y `fair`, que es la referencia del
proyecto). Lo usan `models/data.py` (todas las casas, pre-cierre y cierre), `features.py`
(`mkt_p_*`, `close_p_*`; además guarda `mkt_odds_*`, las cuotas medias tal cual) y la web
(`/api/upcoming` y la ficha del partido, que ahora devuelve también las cuotas en `market.odds`).

Re-ejecutado: `features`, `evaluate`, `market_bias` y `vs_polymarket`. Los hiperparámetros elegidos
en validación no cambian y las predicciones de los modelos propios son idénticas; solo cambia la
referencia y los modelos que usan las probabilidades del mercado como entrada.

| Modelo | Test, proporcional | Test, potencia | vs mercado (potencia) [IC 95 %] |
|---|---|---|---|
| Mercado pre-cierre | 0,9770 | **0,9761** | — |
| Mercado cierre | 0,9760 | 0,9750 | −0,001 [−0,004; +0,002] |
| Elo ajustado con xG | 0,9925 | 0,9925 | +0,016 [+0,009; +0,024] |
| Dixon-Coles xG/goles | 0,9954 | 0,9954 | +0,019 [+0,012; +0,026] |
| Meta-modelo logístico | 0,9950 | 0,9950 | +0,019 [+0,011; +0,027] |
| Mercado recalibrado | 0,9763 | 0,9763 | +0,000 [−0,002; +0,002] |
| Mercado + Dixon-Coles | 0,9766 | 0,9766 | +0,001 [−0,002; +0,003] |
| Mercado + meta-modelo | 0,9785 | 0,9787 | +0,003 [−0,001; +0,006] |

Lectura:
- El mercado con potencia (0,9761) ya es tan bueno como el mercado proporcional recalibrado con una
  logística (0,9763): la recalibración que antes ganaba 0,0007 solo estaba corrigiendo el sesgo del
  método proporcional.
- Los modelos propios quedan ~0,001 más lejos del mercado (Elo ajustado: +0,0155 → +0,0164).
- Polymarket (pre-cierre, n = 1.883): casas 0,9760 frente a 0,9769 de Polymarket (−0,0009
  [−0,0020; +0,0002]); antes estaban empatados. Al cierre, casas 0,9755 frente a 0,9759.
- Apuestas simuladas en test: siguen negativas (Dixon-Coles −21 %, meta-modelo −10 %, árboles −7 %,
  mercado + Dixon-Coles −2 % con 232 apuestas).

## 9. Empates en partidos igualados y equipos ascendidos (15/10/2026)

Motivo: el análisis de errores mostraba que perdemos más frente al mercado en partidos igualados
(favorito < 40 %) y con ascendidos, y `docs/sesgos_mercado.md` que el empate sale ~2 pp más de lo que
dice el mercado en los igualados. La logística de una variable sobre el Elo nunca pasaba del 28 % de empate.

Qué se ha probado (todo dentro de `python -m futdata.models.evaluate`, mismo protocolo: elección en
2024/25, test 2025/26–2026/27 una sola vez, bootstrap emparejado frente al mercado pre-cierre):

1. **Dixon-Coles inflado en empates** (`goals.probs(..., draw_inflation=θ)`): la diagonal del marcador
   se multiplica por 1 + θ antes de normalizar (Poisson inflado en la diagonal, Karlis y Ntzoufras 2003).
   θ ∈ {0; 0,05; 0,1; 0,15; 0,2} se busca junto con ρ. En validación gana θ = 0; la mejor versión
   inflada es θ = 0,05 con ρ = −0,05. También se probó (fuera del banco) una inflación que crece con la
   igualdad del partido: tampoco mejora en validación.
2. **Capa de empate** (`evaluate.draw_features`): logística multinomial con la diferencia de Elo `r`,
   una medida de igualdad (|r| o r²) y log(λ_local + λ_visitante) de Dixon-Coles (menos goles esperados,
   más empates). Elegida en validación: `r, |r|, goles`. El empate previsto llega ya al 35 % (antes 28 %).
3. **Rating inicial de ascendidos por valor de plantilla** (`squads.py`, `ratings.elo(..., squad=,
   value_weight=)`): valor de los 25 jugadores más caros de cada club en Transfermarkt la víspera del
   primer partido de la liga (club según su último traspaso o valoración anterior a esa fecha). En su
   primer partido, el ascendido se re-inicia en (1 − w)·1.400 + w·(rating que predice su valor según la
   recta rating ~ log(valor) de los demás equipos de su liga en ese momento). Elegido en validación:
   w = 0,5. Los ascendidos de 2026/27 no tienen plantilla en el dataset (congelado el 6/7/2026, antes de
   rastrearlos), así que en esa temporada usan el 1.400 fijo; el efecto en test viene casi todo de 2025/26.

Validación 2024/25 (n = 1.752; mercado 0,9633):

| Modelo | Log-loss | vs mercado [IC 95 %] | Igualados (n = 272) | Con ascendido (n = 486) |
|---|---|---|---|---|
| Elo ajustado (referencia) | 0,9722 | +0,009 [+0,001; +0,017] | +0,010 | +0,005 |
| Elo + plantilla | 0,9723 | +0,009 [+0,001; +0,017] | +0,010 | +0,005 |
| Elo + capa de empate | **0,9704** | +0,007 [−0,000; +0,015] | **−0,001** | +0,003 |
| Elo + plantilla + capa de empate | 0,9708 | +0,008 [−0,000; +0,015] | −0,001 | +0,003 |
| Dixon-Coles xG/goles | 0,9751 | +0,012 [+0,005; +0,019] | +0,007 | +0,015 |
| Dixon-Coles inflado (θ = 0,05) | 0,9754 | +0,012 [+0,006; +0,019] | +0,007 | +0,016 |

Test 2025/26–2026/27 (n = 2.049; mercado 0,9761):

| Modelo | Log-loss | vs mercado [IC 95 %] | Igualados (n = 345) [IC] | Con ascendido (n = 569) [IC] | Sin ascendido (n = 1.480) |
|---|---|---|---|---|---|
| Elo ajustado (referencia) | 0,9925 | +0,016 [+0,009; +0,024] | +0,035 [+0,016; +0,054] | +0,030 [+0,013; +0,047] | +0,011 |
| **Elo + plantilla** | **0,9907** | **+0,015 [+0,008; +0,022]** | +0,033 [+0,015; +0,051] | **+0,024 [+0,010; +0,038]** | +0,011 |
| Elo + capa de empate | 0,9936 | +0,018 [+0,010; +0,025] | +0,036 [+0,017; +0,054] | +0,032 [+0,016; +0,049] | +0,012 |
| Elo + plantilla + capa de empate | 0,9917 | +0,016 [+0,009; +0,023] | +0,033 [+0,016; +0,051] | +0,026 [+0,013; +0,041] | +0,012 |
| Dixon-Coles xG/goles | 0,9954 | +0,019 [+0,012; +0,026] | +0,021 [+0,007; +0,036] | +0,038 [+0,024; +0,055] | +0,012 |
| Dixon-Coles inflado (θ = 0,05) | 0,9956 | +0,020 [+0,013; +0,026] | +0,021 [+0,007; +0,036] | +0,039 [+0,024; +0,055] | +0,012 |

Mejora directa frente al modelo de partida en test (log-loss nuevo − base, emparejado; negativo = mejor):

| Cambio | Diferencia [IC 95 %] |
|---|---|
| Elo + plantilla − Elo ajustado | **−0,0018 [−0,0036; −0,00004]** |
| Elo + capa de empate − Elo ajustado | +0,0011 [−0,0016; +0,0036] |
| Elo + plantilla + capa de empate − Elo ajustado | −0,0008 [−0,0037; +0,0022] |
| Dixon-Coles inflado − Dixon-Coles xG/goles | +0,0002 [−0,0002; +0,0004] |

Empate medio previsto en los partidos igualados del test (real 33,3 %, mercado 28,8 %): Elo ajustado
27,9 %, Elo + capa de empate 29,0 %, Dixon-Coles 29,2 %, Dixon-Coles inflado 28,9 %.

Lectura:
- **Ascendidos: mejora pequeña pero real.** El valor de plantilla es el único cambio cuyo intervalo
  frente al Elo ajustado queda (por poco) por debajo de cero: −0,0018 en total, concentrado en los
  partidos con ascendido (+0,030 → +0,024 frente al mercado). Seguimos lejos del mercado en esos
  partidos, que sabe de fichajes de verano que el valor al corte solo recoge en parte. Es el nuevo mejor
  modelo propio: 0,9907 en test, +0,015 [+0,008; +0,022] frente al mercado.
- **Empates: no mejora fuera de muestra.** La capa de empate gana en validación (sobre todo en igualados:
  +0,010 → −0,001) y sube el empate previsto hasta donde lo pone el mercado, pero en test empeora
  +0,001 (IC con el cero) y no reduce el hueco en igualados (+0,035 → +0,036). Inflar la diagonal de
  Dixon-Coles tampoco ayuda en ninguna de las dos muestras. El exceso de empates en igualados del test
  (33 % frente al 29 % del mercado) no lo predice ningún modelo; con n = 345 es compatible con ruido
  (±2,5 pp de error estándar), así que no hay base para forzar más empate del que pone el mercado.
- La distancia al mercado en igualados sigue siendo la mayor (+0,033) y no es un problema de nivel de
  empate: el modelo acierta el empate medio como el mercado y aun así pierde. Lo que falta es información
  sobre qué lado es favorito en partidos parejos (alineaciones, lesiones, forma reciente que el mercado sí ve).
- Ningún cambio altera la conclusión general: ningún modelo propio se acerca a menos de ~0,015 del
  mercado pre-cierre.

## 10. Polymarket por momentos: ¿se equivoca más al abrir? (15/10/2026)

Pregunta: los mercados de Polymarket abren ~13 días antes del partido (mediana 322 h) con poca
liquidez. ¿Hay un tramo inicial en el que nuestro modelo sea mejor y se pueda aprovechar?

Código: `python -m futdata.models.pm_horizons` → `data/processed/polymarket_horizons.json`
(tests en `tests/test_pm_horizons.py`). 1.995 partidos (2025/26 →), precio horario del "Sí" de los
tres mercados 1X2. Modelo: Elo + plantilla (sección 9), fuera de muestra.

**Los precios de apertura no son precios.** Al abrir, cada "Sí" vale ≈ 0,50 (punto medio de un libro
vacío) y los tres suman 1,38 de mediana. Con esos números "ganaríamos" a Polymarket por 0,06 de
log-loss, pero nadie opera a esos precios. Solo se cuentan mercados **formados**: los tres "Sí" suman
entre 0,97 y 1,06, y se normalizan a 1. La suma mediana baja a 1,025 a las 6 h y a 1,005 al día.

Precisión en los mismos partidos (negativo = Polymarket mejor que el modelo):

| Momento | Formados | Polymarket | Modelo | Polymarket − modelo [IC 95 %] |
|---|---|---|---|---|
| Apertura | 40 % | 1,016 | 1,024 | −0,009 [−0,021; +0,005] |
| Apertura + 1 h | 45 % | 1,009 | 1,017 | −0,008 [−0,018; +0,002] |
| Apertura + 6 h | 55 % | 0,989 | 1,004 | −0,014 [−0,024; −0,004] |
| Apertura + 24 h | 75 % | 0,980 | 0,990 | −0,010 [−0,019; −0,001] |
| 10 días antes | 78 % | 0,981 | 0,989 | −0,008 [−0,016; −0,000] |
| 5 días antes | 98 % | 0,980 | 0,993 | −0,013 [−0,020; −0,006] |
| 1 día antes | 100 % | 0,977 | 0,992 | −0,015 [−0,022; −0,007] |
| 1 hora antes | 100 % | 0,975 | 0,991 | −0,016 [−0,024; −0,008] |

(Cada fila usa los partidos formados en ese momento, por eso el log-loss del modelo cambia entre filas.)

Estrategias (comprar el "Sí" del resultado con mayor modelo − precio, coste 0,01 por acción):
- **Mantener hasta el final**: ROI entre −19 % y +1 % según momento y umbral; ningún intervalo por
  encima de cero.
- **Vender 1 h antes del partido** (ganar si el precio se acerca al modelo): entre −7 % y +2,5 %. Solo
  las discrepancias de más de 8 puntos en las primeras 24 h quedan en torno a cero (+0,8 % a +2,5 %,
  intervalos con el cero); el resto pierde de forma significativa. El precio no converge hacia el modelo.

Lectura:
- **No hay ventana temprana.** En cuanto hay operaciones reales, Polymarket ya sabe más que nuestro
  modelo, incluso a 13 días vista.
- **El mercado aprende; el modelo no.** Nuestro modelo usa solo partidos ya jugados, así que sabe lo
  mismo dos semanas antes que el día del partido. Polymarket pasa de ~0,98–0,99 a 0,975 en esos días
  (lesiones, alineaciones, rotaciones, noticias): el hueco con el modelo crece de ~0,009 a ~0,016.
  Encaja con la sección 6: el once titular explica el 10 % del movimiento de la cuota hasta el cierre.
- Limitaciones: el precio histórico es el de la API (punto medio o última operación), no la horquilla
  real ni la profundidad del libro; con poca liquidez el coste real sería mayor que 0,01.
