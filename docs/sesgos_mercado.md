# Sesgos del mercado 1X2 y estrategias a la mejor cuota

Fecha: 15/10/2026. Script: `python -m futdata.models.market_bias` → `data/processed/market_bias.json`.
Complementa `docs/modelos.md` (fase 5).

## 0. Protocolo

- Partidos de las cinco grandes ligas con cuota media pre-cierre: 9.204.
- Periodos: **descubrimiento** 2021/22–2023/24 (5.403), **validación** 2024/25 (1.752),
  **test** 2025/26–2026/27 (2.049). Los umbrales de cada estrategia se eligen en descubrimiento y
  luego no se tocan; Betfair Exchange solo existe desde 2024/25, así que su umbral se elige en validación.
- Las señales usan solo la cuota media pre-cierre (viernes o martes) sin margen con Shin, que
  calcula el propio script a partir de las cuotas (no depende del método que use el resto del proyecto). La apuesta se
  hace a la cuota pre-cierre de cada casa: **mejor cuota** (Max de Football-Data), Bet365, Betfair
  Exchange (comisión del 5 % sobre la ganancia) y la media.
- Apuesta plana de 1 unidad. ROI con intervalo *bootstrap* al 95 %. **CLV** = valor esperado de cada
  apuesta con la probabilidad de cierre sin margen (media de casas, Shin): converge mucho antes que el ROI.

## 1. Quitar el margen: proporcional, Shin y potencia

Margen medio pre-cierre: media de casas 4,9 %, Bet365 5,5 %, **mejor cuota 0,8 %**, Betfair 0,8 % (más comisión).

Pendiente de calibración (logística del acierto de cada selección sobre el logit de su probabilidad;
1 = bien calibrado, > 1 = el mercado se queda corto en los extremos, es decir, sesgo favorito-longshot):

| Método (cuota media pre-cierre) | Pendiente descubr. / valid. / test | Log-loss test | Frente a proporcional (test) |
|---|---|---|---|
| Proporcional (el que usamos) | 1,080 / 1,086 / 1,098 | 0,9770 | — |
| Shin | 1,038 / 1,040 / 1,037 | 0,9762 | −0,0008 [−0,0017; +0,0003] |
| Potencia | 1,019 / 1,019 / 1,011 | 0,9761 | −0,0009 [−0,0024; +0,0007] |

Con la cuota de cierre sale lo mismo (proporcional 1,10 en test; Shin 1,04; potencia 1,02).

Lectura:
- El método proporcional **deja un sesgo favorito-longshot sistemático**: la pendiente es > 1 en
  los tres periodos y en los dos momentos. Por tramos (todas las temporadas), las selecciones con
  p ≤ 0,1 ganan un 5,6 % frente al 7,6 % implícito (z = −2,1) y las de 0,6–0,7 ganan un 68,3 % frente
  al 64,8 % (z = +2,7).
- Shin lo reduce a la mitad y el método de potencia casi lo elimina; con Shin ningún tramo se
  separa más de |z| = 1,7.
- La mejora en log-loss es pequeña (≈0,0005–0,0009), siempre en la misma dirección, pero ningún
  intervalo por periodo excluye el cero. Es un cambio de calibración en las colas, no de capacidad
  predictiva.
- **Consecuencia práctica (aplicada el 15/10/2026)**: desde esta fecha todo el proyecto quita el
  margen con el método de potencia (`futdata/models/margin.py`, función `fair`): `data.py`,
  `features.py`, `evaluate.py` y la web. Ver `docs/modelos.md`, sección 8.

## 2. Empates en partidos igualados

Frecuencia de empate frente a la probabilidad de empate (Shin), según lo igualado del partido
|p_local − p_visitante|:

| Igualdad | n | Empates reales | Implícito | z |
|---|---|---|---|---|
| < 0,1 | 1.826 | 30,6 % | 28,4 % | +2,1 |
| 0,1–0,2 | 1.760 | 28,3 % | 27,8 % | +0,5 |
| 0,2–0,3 | 1.383 | 28,4 % | 26,5 % | +1,6 |
| 0,3–0,4 | 1.317 | 24,9 % | 24,7 % | +0,2 |
| 0,4–0,6 | 1.852 | 21,8 % | 21,2 % | +0,6 |
| > 0,6 | 1.057 | 14,4 % | 14,5 % | −0,1 |

- En los partidos más igualados el empate sale ~2 puntos más de lo que dice el mercado, **con el mismo
  signo en los tres periodos** (+2,1, +2,5 y +2,3 puntos), aunque por separado ninguno es significativo.
- Por liga (igualdad < 0,15) se concentra en Italia (32,9 % frente a 29,2 %) y España (32,9 % frente
  a 29,7 %); Alemania, Inglaterra y Francia están calibradas. Es un corte hecho a posteriori: hay que
  tratarlo como hipótesis, no como resultado.

## 3. Estrategias

Tres familias, con el umbral elegido en descubrimiento (máximo ROI con ≥ 200 apuestas):
- **Favorito**: apostar al favorito si su probabilidad (Shin) supera t.
- **Empate igualado**: apostar al empate si |p_local − p_visitante| < t.
- **Valor Shin**: apostar al resultado con p_Shin × cuota − 1 > t. Solo tiene sentido con la mejor
  cuota o Betfair: con la media o Bet365 el margen hace que casi nunca haya valor.

| Estrategia | Casa | t | Descubrimiento | Validación | Test | Fuera de muestra (valid. + test) | CLV fuera de muestra |
|---|---|---|---|---|---|---|---|
| Favorito | mejor cuota | 0,65 | +2,6 % [−1,1; +6,2] | +2,7 % | +2,3 % | **+2,5 % [−1,6; +6,5]**, n = 750 | −1,1 % |
| Favorito | Bet365 | 0,65 | −1,1 % | +0,1 % | +0,5 % | +0,3 % [−3,7; +4,2] | −3,2 % |
| Favorito | Betfair (−5 %) | 0,70 | — | +4,1 % | +0,4 % | +0,4 % [−6,6; +7,0] (solo test) | −2,5 % |
| Favorito | media | 0,65 | −0,2 % | +0,2 % | −0,2 % | 0,0 % [−4,0; +3,9] | −3,5 % |
| Empate igualado | mejor cuota | 0,25 | **+7,9 % [+1,6; +14,5]** | +0,5 % | +1,7 % | +1,2 % [−6,7; +8,7], n = 1.769 | −1,0 % |
| Empate igualado | Bet365 | 0,25 | +2,2 % | −4,6 % | −1,1 % | −2,6 % | −4,8 % |
| Empate igualado | Betfair (−5 %) | 0,10 | — | +1,6 % | −0,2 % | −0,2 % (solo test) | −5,3 % |
| Empate igualado | media | 0,25 | +3,0 % | −4,0 % | −1,7 % | −2,8 % | −4,9 % |
| Valor Shin | mejor cuota | 0,03 | +2,6 % | −19,2 % | −2,9 % | −12,7 % [−43; +22], n = 136 | +9,4 % |
| Valor Shin | Betfair (−5 %) | 0,00 | — | −8,9 % | −7,6 % | −7,6 % (solo test) | −1,2 % |

Lectura:
1. **Ninguna estrategia es rentable de forma demostrable.** Ningún intervalo fuera de muestra
   excluye el cero.
2. **Favorito a la mejor cuota** es la más estable: +2,6 %, +2,7 % y +2,3 % en los tres periodos.
   Es justo lo que predice el sesgo favorito-longshot de la sección 1. Pero el CLV es negativo fuera
   de muestra (la cuota no se mueve a favor), la ganancia depende de conseguir la mejor cuota del
   mercado en cada partido y desaparece con una sola casa (Bet365, media). Además no es monótona en
   el umbral (t = 0,6 da −1,8 % en validación), señal de que gran parte es ruido.
3. **Empate igualado** es el ejemplo de libro de sobreajuste: +7,9 % significativo en descubrimiento,
   ≈ +1 % fuera de muestra. El sesgo de la sección 2 existe, pero 2 puntos de probabilidad sobre un
   empate a cuota ~3,5 (mejor cuota) apenas cubren el 0,8 % de margen de la mejor cuota y no cubren el de una sola casa.
4. **Valor Shin a la mejor cuota** tiene CLV muy positivo (+9 %) y ROI negativo. Las cuotas que más
   se separan del resto suelen ser precios desfasados o de casas que limitan: el "valor" aparece
   justo donde la cuota máxima es menos creíble. Es una advertencia sobre usar Max de Football-Data
   como cuota alcanzable.
5. Se han probado 3 familias × 4 casas × 5–6 umbrales (≈ 60 combinaciones). Con ese número, que
   alguna salga significativa en un periodo es lo esperable por azar (el empate en descubrimiento).
   Por eso solo cuenta lo que se mantiene fuera de muestra.

## 4. Limitaciones

- La mejor cuota de Football-Data es el máximo entre ~10 casas en el momento de la captura. En la
  práctica exige cuentas en todas ellas y las casas limitan a quien gana: el ROI a la mejor cuota es
  una cota superior.
- Solo hay dos fotos de la cuota (pre-cierre y cierre). Sin cuotas con hora no se puede estudiar
  cuándo se corrige cada sesgo ni apostar en el mejor momento.
- Betfair solo cubre 2024/25 en adelante; la comisión real depende del país y del volumen.
- El test 2026/27 está en curso (≈300 partidos).

## 5. Qué hacer con esto

1. ~~Cambiar la referencia del mercado a Shin o potencia~~ **Hecho** con potencia (15/10/2026). Era la
   única conclusión firme: calibra mejor en todos los periodos.
2. **Llevar el empate al modelo propio**: un modelo que suba el empate en partidos igualados
   (Poisson bivariante o inflado en empates, o una multinomial que dependa de la igualdad) atacaría
   el mismo hueco que se ve en el mercado y en nuestros errores (`docs/modelos.md`).
3. **Seguir midiendo de forma prospectiva** la estrategia de favorito a la mejor cuota, con un
   umbral fijo de 0,65 y registrando la cuota realmente disponible. Con ~400 apuestas por temporada,
   distinguir un +2,5 % de cero exige varias temporadas.
4. Buscar sesgos en los mercados de más/menos 2,5 y hándicap asiático, que tenemos y aún no hemos
   estudiado.
