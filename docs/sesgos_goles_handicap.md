# Sesgos de los mercados de más/menos 2,5 y hándicap asiático

Fecha: 15/10/2026. Script: `python -m futdata.models.market_bias_goals` → `data/processed/market_bias_goals.json`
(~15 s). Tests: `tests/test_market_bias_goals.py`. Complementa `docs/sesgos_mercado.md` (1X2), cuyo
protocolo se repite aquí sin cambios.

**Respuesta corta: no hay sesgos explotables en ninguno de los dos mercados.** Ninguna de las 160
combinaciones probadas (familia × casa × umbral) da un ROI fuera de muestra cuyo intervalo excluya el
cero por arriba, y todas las elegidas tienen CLV negativo con una sola casa. Son mercados tan
eficientes como el 1X2, no menos.

## 0. Protocolo

- Partidos de las cinco grandes ligas, 2021/22–2026/27. Más/menos: 9.204 con cuota media pre-cierre.
  Hándicap: 9.161 (se descartan 43 de 2025/26 con cuotas erróneas, ver abajo).
- Periodos: **descubrimiento** 2021/22–2023/24 (5.403), **validación** 2024/25 (1.752), **test**
  2025/26–2026/27 (2.049 / 2.006). Umbrales elegidos en descubrimiento; Betfair Exchange (desde 2024/25)
  en validación. "Fuera de muestra" junta los periodos posteriores al de elección.
- Señales con la cuota media pre-cierre sin margen (método de potencia, el del proyecto). Apuesta plana
  de 1 unidad a la cuota pre-cierre de la **mejor cuota** (Max), **Bet365**, **Betfair** (comisión del 5 %
  sobre la ganancia) y la **media**. ROI con *bootstrap* al 95 %. **CLV** = p de cierre (media, potencia)
  × cuota − 1.
- **Liquidación del hándicap asiático** (`ah_split`, con tests): AHh es la línea del local
  (−0,75 = el local da 0,75 goles). Líneas de .5 sin devolución; líneas enteras con *push* (se
  devuelve la apuesta); líneas de cuarto partidas en dos medias apuestas (−0,75 = mitad a −0,5 y mitad
  a −1: si el local gana por uno, media ganada y media devuelta). Con fracción ganada w y perdida l, el
  beneficio es w·(cuota − 1) − l y la probabilidad justa es w/(w + l); por eso la calibración usa como
  resultado y = w/(w + l) con peso w + l (0 en push, 0,5 en medio push).
- En el hándicap, la cuota de cierre es de la línea de cierre (AHCh), que solo coincide con la
  pre-cierre en el **64 %** de los partidos. El CLV se calcula solo en esos; para todos se registra si
  la línea se movió a favor o en contra de la apuesta.
- **Limpieza de datos**: en 2025/26 hay ~40 partidos de hándicap con una casa a 22,00 que infla la
  cuota media y la máxima (salía un ROI "de +689 %" en test). Se descarta la cuota media o de cierre
  sin margen positivo y la mejor cuota más de un 25 % por encima de la media. En más/menos solo afecta
  a un puñado de mejores cuotas.

## 1. Quitar el margen

Margen medio pre-cierre:

| | Media | Bet365 | Mejor cuota | Betfair (sin comisión) |
|---|---|---|---|---|
| Más/menos 2,5 | 5,3 % | 4,9 % | 1,8 % | 1,8 % |
| Hándicap asiático | 4,5 % | 3,1 % | 1,5 % | 1,2 % |

El margen es parecido al del 1X2 (4,9 % la media), pero la **mejor cuota es más cara** que en 1X2
(1,8 % y 1,5 % frente a 0,8 %): hay menos dispersión entre casas que aprovechar.

### Más/menos 2,5

| Método (media pre-cierre) | Pendiente descubr. / valid. / test | Log-loss test | Frente a proporcional (test) |
|---|---|---|---|
| Proporcional | 1,191 / 1,068 / 1,095 | 0,6710 | — |
| Shin | 1,127 / 1,006 / 1,018 | 0,6708 | −0,0002 [−0,0008; +0,0004] |
| Potencia | 1,095 / 0,976 / 0,983 | 0,6708 | −0,0002 [−0,0011; +0,0007] |

Al cierre: 0,6679 con potencia (pendientes 1,078 / 1,007 / 0,987).

- Igual que en 1X2, el proporcional deja algo de favorito-longshot (pendiente > 1 en los tres
  periodos) y la potencia lo corrige. En descubrimiento la potencia mejora −0,0004 [−0,0008; +0,0001].
  En un mercado de dos opciones casi parejas (más/menos ≈ 53/47) la diferencia es minúscula.
- El mercado de más/menos predice ~0,671 frente a log 2 = 0,693: el número de goles es mucho más
  difícil de predecir que el 1X2, y las casas apenas tienen información que aprovechar.

### Hándicap asiático

Log-loss ponderado (pre-cierre, potencia): 0,6917 / 0,6912 / 0,6931 en los tres periodos, es decir,
**≈ log 2 = 0,6931**. Es lo esperado: la línea se pone para que las dos partes estén al 50 %, y las
probabilidades sin margen se mueven entre 0,45 y 0,55. Por eso la pendiente de calibración no es
informativa aquí (sale 1,18 / 1,28 / 0,51 con intervalos enormes) y los tres métodos dan lo mismo
(diferencias ≤ 0,0001 salvo ruido). La prueba útil es la de la sección 2: si un lado cubre más de lo
que implica su cuota.

## 2. Sesgos

### 2.1 Más/menos 2,5: frecuencia real frente a implícita

Por tramo de p(más de 2,5) (potencia), todas las temporadas: **ningún tramo se separa más de
|z| = 1,2** (p.ej. 0,40–0,45: 40,9 % real frente a 42,7 %; 0,65–0,70: 69,4 % frente a 67,2 %). En el
global, 53,1 % frente a 53,0 % en descubrimiento, 53,4 % frente a 53,9 % en validación, 54,2 % frente a
53,1 % en test.

Por liga (todas las temporadas):

| Liga | n | Más de 2,5 real | Implícito | z |
|---|---|---|---|---|
| Alemania | 1.575 | 61,5 % | 60,2 % | +1,0 |
| Inglaterra | 1.960 | 56,6 % | 56,2 % | +0,4 |
| Francia | 1.732 | 53,8 % | 53,5 % | +0,2 |
| Italia | 1.959 | 49,1 % | 49,9 % | −0,7 |
| España | 1.978 | 47,8 % | 47,7 % | +0,1 |

El mercado conoce perfectamente la diferencia de goles entre ligas. No hay ningún sesgo hacia el
"más" (el apostante recreativo prefiere goles, pero no se ve en el precio). En el test la Bundesliga
sale +4 puntos (65,5 % frente a 61,5 %, z = +1,6), con el signo contrario en validación: ruido.

### 2.2 Hándicap asiático: ¿cubre el favorito?

Favorito = el que da goles con la línea (línea ≠ 0). Cobertura ponderada frente a la implícita:

| |línea| | n | Cubre el favorito | Implícito | z | Descubr. / valid. / test |
|---|---|---|---|---|---|
| 0,25 | 2.474 | 51,4 % | 49,5 % | +1,7 | 51,1 / 48,5 / 54,4 % |
| 0,5 | 1.629 | 48,3 % | 49,5 % | −1,0 | 48,4 / 50,2 / 46,6 % |
| 0,75 | 1.339 | 50,7 % | 50,1 % | +0,4 | 51,0 / 54,4 / 46,2 % |
| 1 | 656 | 48,8 % | 49,8 % | −0,5 | 50,9 / 39,0 / 52,7 % |
| 1,25–1,5 | 1.163 | 49,7 % | 49,6 % | +0,1 | 50,0 / 47,2 / 51,4 % |
| **≥ 1,75** | 567 | **44,3 %** | 49,7 % | **−2,5** | 42,4 / 43,8 / 50,0 % |

- En global el favorito cubre lo que dice la cuota (49,7 % frente a 49,7 % en descubrimiento).
- **Favoritos muy claros (línea ≥ 1,75)**: cubren ~5 puntos menos de lo implícito en descubrimiento
  (z = −2,6) y validación, pero no en test (50,0 %). Es el sesgo favorito-longshot "al revés" que a
  veces se describe en el hándicap (el público apuesta al grande y la línea se estira de más). Con 567
  partidos y una de seis filas buscada a posteriori, es una hipótesis, no un resultado.
- Por liga, ninguna |z| > 1,7 (España 51,6 % frente a 49,5 %; Inglaterra 47,9 % frente a 49,7 %).
- **Local en 2024/25**: el local cubrió el 45,6 % frente al 49,9 % implícito (z = −3,3), en las cinco
  ligas; en descubrimiento −0,4 puntos y en test +1,4. Fue una temporada de ventaja de local baja que
  el mercado tardó en descontar, no un sesgo estable: no se puede elegir de antemano.

## 3. Estrategias

Familias (umbral elegido en descubrimiento, máximo ROI con ≥ 200 apuestas):
- Más/menos: **más** (p_más > t), **menos** (p_más < t), **valor** (p × cuota − 1 > t), **DC
  diferencia** (apostar al lado que el modelo Dixon-Coles xG/goles ve más de t puntos por encima del
  mercado) y **DC valor** (p_modelo × cuota − 1 > t).
- Hándicap: **favorito** y **no favorito** con |línea| ≥ t, y **valor**.

### 3.1 Más/menos 2,5 (mejor cuota, y la mejor alternativa por familia)

| Estrategia | Casa | t | Descubrimiento | Validación | Test | Fuera de muestra | CLV fuera de muestra |
|---|---|---|---|---|---|---|---|
| Más | mejor cuota | 0,60 | +2,5 % [−1,8; +6,6] | −2,9 % | −2,3 % | −2,6 % [−7,0; +1,9], n = 994 | −1,3 % |
| Más | Bet365 | 0,60 | −0,5 % | −4,9 % | −3,4 % | −4,2 % [−8,6; 0,0] | −2,8 % |
| Menos | mejor cuota | 0,40 | +4,5 % [−2,9; +11,8] | −1,4 % | −12,1 % | −6,8 % [−15,2; +1,5], n = 323 | −0,6 % |
| Menos | Betfair (−5 %) | 0,45 | — | +0,5 % | −8,3 % | −8,3 % [−15,8; −0,3] (solo test) | −2,1 % |
| Valor | mejor cuota | 0,01 | +6,5 % [−1,7; +15,3] | −5,4 % | −58 % (n = 14) | −18,9 % [−41,9; +4,9], n = 55 | +4,1 % |
| DC diferencia | mejor cuota | 0,10 | +5,3 % [−8,3; +18,9] | +18,2 % | −10,7 % | +0,5 % [−13,5; +15,0], n = 255 | −3,9 % |
| DC diferencia | Betfair (−5 %) | 0,08 | — | +1,9 % | −8,6 % | −8,6 % [−22,2; +5,2] (solo test) | −4,7 % |
| DC valor | mejor cuota | 0,04 | −0,3 % [−4,9; +4,3] | −3,0 % | −9,8 % | **−6,2 % [−11,2; −1,3]**, n = 1.857 | −3,1 % |
| DC valor | media | 0,00 | −3,7 % | −7,2 % | −11,9 % | **−9,5 % [−14,1; −5,0]** | −6,4 % |

**Modelo Dixon-Coles xG/goles frente al mercado** (log-loss de más/menos, mismos partidos):

| Periodo | n | Modelo | Mercado pre-cierre | Cierre | Modelo − mercado |
|---|---|---|---|---|---|
| Descubrimiento (2022/23–23/24) | 3.578 | 0,6738 | 0,6677 | 0,6657 | +0,0060 [+0,0021; +0,0100] |
| Validación | 1.752 | 0,6738 | 0,6687 | 0,6650 | +0,0051 [−0,0001; +0,0100] |
| Test | 2.049 | 0,6803 | 0,6708 | 0,6679 | +0,0095 [+0,0043; +0,0150] |

El modelo es **significativamente peor que el mercado** en más/menos (correlación 0,84–0,89 con él).
Cuando se separa del mercado, quien tiene razón suele ser el mercado: apostar donde el modelo ve
valor pierde de forma significativa fuera de muestra (−6 % a la mejor cuota, −9,5 % a la media), con
CLV negativo. Con un umbral alto (diferencia > 0,10) sale +18 % en validación y −11 % en test sobre
~100–150 apuestas: ruido.

### 3.2 Hándicap asiático

| Estrategia | Casa | t | Descubrimiento | Validación | Test | Fuera de muestra | CLV / línea a favor–en contra |
|---|---|---|---|---|---|---|---|
| Favorito | mejor cuota | 0,25 | −0,8 % [−3,4; +1,8] | −3,5 % | −2,0 % | −2,7 % [−5,7; +0,4], n = 3.313 | −2,1 % / 16–21 % |
| Favorito | media | 0,25 | −3,2 % | −5,9 % | −4,8 % | **−5,3 % [−8,3; −2,3]** | −5,1 % |
| No favorito | mejor cuota | 1,5 | **+9,7 % [+2,5; +17,3]** | +5,8 % | −4,3 % | +0,9 % [−7,8; +9,4], n = 449 | −2,4 % / 28–22 % |
| No favorito | Bet365 | 1,5 | +7,3 % [+0,4; +14,6] | +4,3 % | −5,0 % | −0,2 % [−8,8; +8,1] | −3,8 % |
| No favorito | Betfair (−5 %) | 1,0 | — | +5,6 % | −7,1 % | −7,1 % [−14,3; +0,8] (solo test) | −4,6 % |
| No favorito | media | 1,5 | +6,4 % | +3,0 % | −7,3 % | −2,0 % [−10,4; +6,2] | −5,6 % |
| Valor | mejor cuota | 0,01 | +2,2 % [−8,6; +12,5] | −5,5 % | +29,6 % (n = 17) | +5,8 % [−17,2; +29,4], n = 53 | +2,3 % |

Lectura:
1. **Ninguna estrategia es rentable de forma demostrable** en ninguno de los dos mercados. Los
   intervalos fuera de muestra incluyen el cero o están por debajo.
2. **No favorito con línea ≥ 1,5** es la única pista que recuerda a un sesgo: +9,7 % significativo en
   descubrimiento (es la sección 2.2 vista como apuesta), aguanta en validación (+5,8 %) y desaparece
   en test (−4,3 %). Es el mismo patrón que el "empate igualado" del 1X2: un efecto descubierto mirando
   muchas filas que se diluye fuera de muestra. Además el CLV es negativo y en la rejilla el ROI no es
   monótono en el umbral (con t = 1,0 sale −5,4 % en test).
3. **Más/menos** no tiene ni siquiera una pista: las familias "más" y "menos" ganan algo en
   descubrimiento y pierden en los dos periodos siguientes. La preferencia del público por el "más" no
   se traduce en precios mal puestos.
4. **Valor a la mejor cuota** vuelve a dar CLV positivo y ROI inestable sobre muy pocas apuestas, como
   en 1X2: las cuotas máximas que más se separan de la media son las menos alcanzables. Tras limpiar
   los errores de 2025/26 quedan 55 apuestas en más/menos y 53 en hándicap: no se puede concluir nada.
5. Pruebas: 100 combinaciones en más/menos (5 familias × 4 casas × 5 umbrales) y 60 en hándicap.
   Con 160 intentos, uno o dos significativos en descubrimiento es lo esperable por azar.

## 4. Limitaciones

- Solo dos fotos de la cuota (pre-cierre y cierre). En el hándicap la línea se mueve en el 36 % de los
  partidos y entonces no hay CLV comparable: el CLV del hándicap se calcula sobre el 64 % restante.
- Las cuotas de Betfair en el hándicap se suponen de la misma línea AHh que la media (Football-Data no
  da la línea por casa).
- La "mejor cuota" es el máximo entre casas en el momento de la captura: cota superior de lo alcanzable,
  y con errores de datos (sección 0) que obligan a filtrarla.
- Solo la línea de 2,5 goles; las líneas asiáticas de goles (2,25, 2,75…) no están en Football-Data.
- El modelo Dixon-Coles empieza en 2022/23 (walk-forward), así que su descubrimiento tiene dos
  temporadas. Sus probabilidades vienen de `model_predictions.parquet` tal como estaba el 15/10/2026;
  si se reentrena el modelo, basta con volver a ejecutar el script.

## 5. Qué hacer con esto

1. **Cerrar la búsqueda de sesgos simples** en estos mercados con estos datos: con 1X2, más/menos y
   hándicap, la conclusión es la misma (mercado eficiente; los "sesgos" no sobreviven fuera de muestra).
2. **Seguir de forma prospectiva** solo una hipótesis, con regla fija: apostar al no favorito con línea
   ≥ 1,5 a la mejor cuota, registrando la cuota realmente disponible. Con ~200 apuestas por temporada,
   hacen falta varias para distinguir +5 % de cero.
3. El modelo de goles **no aporta en más/menos** frente al mercado (+0,005–0,010 de log-loss). Si se
   quiere usar, que sea en combinación con el mercado (como el "Mercado + Dixon-Coles" del 1X2), no
   como señal de apuesta.
