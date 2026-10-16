# Guía de diseño del frontend: analítica 1X2 frente al mercado

Objetivo: una herramienta de análisis con el nivel de acabado de Linear, Vercel o Stripe. No queremos una landing page de apuestas. El producto es el dato: probabilidad del modelo frente a probabilidad implícita del mercado, y la evidencia que la sostiene (xG, forma, Elo, momentum).

---

## 1. Principios (12, verificables)

1. **El número primero, el adorno nunca.** Cada pantalla responde una pregunta en menos de 5 s ("¿quién gana según el modelo y en qué discrepa del mercado?"). Verificación: tapa los gráficos y comprueba que la respuesta sigue siendo legible en texto.
2. **Un solo color de acento.** El resto de la interfaz va en grises. El color se reserva para datos con significado (local, empate, visitante, ventaja positiva o negativa). Verificación: en una captura en escala de grises no se pierde jerarquía.
3. **Densidad tipo Linear.** Filas de tabla de 36 px, texto base de 14 px, nada de tarjetas gigantes. Verificación: un portátil de 1440×900 muestra al menos 15 partidos sin hacer scroll.
4. **Cifras tabulares y alineadas a la derecha.** Todas las cifras van con `font-variant-numeric: tabular-nums` y los decimales coinciden en cada columna.
5. **Formato español.** Coma decimal (`0,42`), porcentajes con espacio fino (`54 %`), fechas tipo `sáb 18 oct · 21:00` y horas en Europe/Madrid.
6. **La URL guarda el estado.** Liga, temporada, jornada, pestaña y filtros viven en la query string, así que recargar o pulsar Atrás no pierde contexto (Vercel Web Interface Guidelines).
7. **Todo se maneja con teclado.** Hay ⌘K, `J`/`K` para moverse entre filas, `/` para buscar y un anillo de foco visible con `:focus-visible`.
8. **El movimiento responde a la acción del usuario y nunca decora.** Duración de 150 a 250 ms, solo `transform` y `opacity`, y nada de animaciones en acciones de teclado (Emil Kowalski, rauno).
9. **Cada estado está diseñado.** Vacío, cargando (skeleton con la misma geometría), error con salida y partido aún sin cuotas.
10. **La incertidumbre se ve.** Ninguna probabilidad aparece sin contexto: se muestran la calibración, el tamaño de muestra y el margen de la casa eliminado.
11. **El modelo frente al mercado usa siempre la misma codificación.** Modelo = trazo sólido con el color de acento. Mercado = trazo gris discontinuo o marcador hueco. Se aplica en todos los gráficos sin excepción.
12. **El texto es de producto, no de marketing.** Va en tono de frase ("Próximos partidos", no "Descubre el poder de la predicción"), con verbos concretos en los botones y errores que dicen qué pasó y cómo arreglarlo.

---

## 2. Referentes y qué copiar de cada uno

| Referente | Qué copiar exactamente |
|---|---|
| **Linear** | Rediseño con el color generado en LCH a partir de 3 variables (base, acento, contraste). El azul queda limitado para conseguir un aspecto neutro. Usa Inter Display en titulares e Inter en el resto. La barra lateral alinea iconos y etiquetas en vertical y horizontal. Copiar: superficies por niveles de luminosidad (fondo, panel, diálogo), barra lateral sobria, ⌘K y atajos visibles en los tooltips. |
| **Vercel / Geist** | Escala tipográfica con roles (Heading, Label, Copy, Button) en lugar de tamaños sueltos, variantes `-mono` para datos, bordes de 1 px en lugar de sombras y pestañas subrayadas. Copiar: la nomenclatura de tokens y el uso de Geist Mono para cifras. |
| **Stripe (dashboard y docs)** | Sistema de color accesible construido en CIELAB: dos tonos separados por 5 niveles garantizan contraste para texto pequeño, y por 4 niveles para iconos. Los badges suben un nivel el fondo y el texto. Copiar: la regla de "5 niveles" para generar la escala de grises y de color, y las tablas con cifras alineadas y hover sutil. |
| **Ramp / Mercury** | Tablas financieras limpias: cifras grandes sin decoración, variaciones en gris con signo explícito (+2,1 pp) y gráficos de área monocromos. Copiar: el tratamiento de "dinero" aplicado a probabilidades y valor esperado. |
| **Raycast** | La paleta de comandos como navegación principal, con resultados agrupados, atajo a la derecha y previsualización. Copiar: ⌘K con grupos *Partidos / Equipos / Ligas / Acciones*. |
| **Resend / Supabase** | Documentación y dashboard en modo oscuro con un único acento y código o datos en mono. Copiar: la página de metodología del modelo con aspecto de docs técnicos. |
| **PostHog** | Gráficos de producto con tooltip rico y comparación entre periodos. Copiar: un tooltip que muestre ambas series (modelo y mercado) con su diferencia. |
| **Attio / Cal.com** | Tablas tipo base de datos con columnas configurables, filtros como "chips" en una barra superior y vistas guardadas. Copiar: los filtros de liga, jornada y "solo con ventaja > 5 pp". |
| **Arc** | Barra lateral que se puede plegar y espacios separados. Copiar con moderación: barra lateral plegable a solo iconos (56 px). |
| **The Athletic** | Jerarquía editorial y tipografía de lectura excelente. Copiar: el bloque "Por qué" de cada partido en prosa breve con cifras incrustadas. |
| **FotMob** | Gráfico de momentum de barras divergentes por minuto (lanzado en 2023), mapa de tiros con tamaño proporcional al xG y ficha de partido con pestañas. Copiar: la estructura de la ficha (Resumen · Estadísticas · Tiros · Momentum · Alineaciones). |
| **Opta Analyst** | Páginas de predicciones con probabilidades como cifra etiquetada y hubs de métricas avanzadas. Copiar: la tabla de predicción de liga con barras 1X2 apiladas. |
| **StatsBomb IQ** | Campo sobrio con líneas finas y marcadores con significado (relleno = gol). Copiar: la convención de mapa de tiros. |
| **Polymarket / Kalshi** | La probabilidad como número protagonista, la curva de probabilidad con área sombreada y selector de rango (6H/1D/1S/1M/Todo). Copiar: la evolución de la probabilidad implícita del mercado a lo largo de la semana previa, con la línea del modelo superpuesta. |

**Dribbble** (tags *web-design*, *sports betting dashboard*, *football prediction dashboard*, *fantasy football*). Hay que filtrar mucho.
- *Funciona:* tablas densas con escudo, nombre y cifras; barra 1X2 apilada; listas de partidos agrupadas por fecha; modo oscuro con un acento.
- *Es adorno y se descarta:* fotos de jugadores recortadas sobre gradientes, donuts "de relleno" sin datos reales, tarjetas de métricas con flechas verdes inventadas, neón o glassmorphism, tipografía display gigante dentro del dashboard, campos 3D en perspectiva y "AI-Powered" en los titulares.

---

## 3. Sistema visual recomendado

### Tipografía
- **Geist Sans** para la interfaz y **Geist Mono** para cifras, cuotas y minutos. Licencia OFL. Instálala desde el paquete npm `geist` o el .zip, no desde Google Fonts: Vercel indica que la versión de Google Fonts no trae el juego completo de glifos ni `font-feature-settings`, y necesitamos `tnum`.
- Alternativa si se quiere huir del look Vercel: **IBM Plex Sans + IBM Plex Mono** (OFL).
- Evita Inter por defecto, Space Grotesk y las combinaciones serif más sans.
- Escala (px / interlineado / peso):

| Token | Tamaño | Interlineado | Peso | Uso |
|---|---|---|---|---|
| `display` | 32 | 38 | 600, tracking −0,02em | Título de página (solo uno) |
| `h2` | 20 | 28 | 600 | Sección |
| `h3` | 16 | 24 | 600 | Subsección o cabecera de panel |
| `body` | 14 | 20 | 400 | Texto general |
| `label` | 13 | 18 | 500 | Etiquetas, tabs, sidebar |
| `caption` | 12 | 16 | 400 | Notas, ejes |
| `num-xl` | 28 | 32 | 500 mono | Probabilidad protagonista |
| `num` | 13 | 18 | 400 mono | Cifras en tabla |

En móvil, los inputs llevan como mínimo 16 px.

### Paleta (tokens semánticos)

**Modo oscuro (por defecto):**
| Token | Hex |
|---|---|
| `bg` | `#0C0D0F` |
| `surface-1` (paneles) | `#141518` |
| `surface-2` (hover, popover) | `#1B1C20` |
| `border` | `#26282D` |
| `border-strong` | `#34363C` |
| `text` | `#EDEDEF` |
| `text-muted` | `#A0A1A8` |
| `text-subtle` | `#6B6D75` |
| `accent` (modelo, foco, enlaces) | `#4CC38A` (verde césped desaturado) |

**Modo claro:**
| Token | Hex |
|---|---|
| `bg` | `#FBFBFA` |
| `surface-1` | `#FFFFFF` |
| `surface-2` | `#F3F3F1` |
| `border` | `#E6E6E3` |
| `border-strong` | `#D4D4CF` |
| `text` | `#18181B` |
| `text-muted` | `#5F6068` |
| `text-subtle` | `#8B8C93` |
| `accent` | `#18794E` |

**Colores de datos (iguales en los dos modos, ajustados de luminosidad):**
| Significado | Oscuro | Claro |
|---|---|---|
| Local (1) | `#5B9BF0` | `#2563C9` |
| Empate (X) | `#8E9096` | `#7A7C83` |
| Visitante (2) | `#E5A54B` | `#B7741A` |
| Ventaja positiva (modelo > mercado) | `#4CC38A` | `#18794E` |
| Ventaja negativa | `#E5616B` | `#C4323D` |
| Gol en mapa de tiros | relleno del color del equipo | |
| Escala de calor (secuencial, una sola tonalidad) | de `#141518` a `#4CC38A` | de `#FFFFFF` a `#18794E` |

Azul frente a ámbar es un par seguro para daltónicos, y no se usa rojo frente a verde para local y visitante. Genera las escalas en OKLCH/LCH (Linear, Stripe) y comprueba el contraste con APCA o WCAG: 4,5:1 para texto pequeño. Declara `color-scheme: dark`.

### Espaciado, radios y bordes
- Escala de 4 px: `4, 8, 12, 16, 24, 32, 48`. Paneles con padding de 16 px y separación entre secciones de 32 px.
- Radios: inputs y botones 6 px, paneles 8 px, diálogos 12 px. Nunca más. Los radios anidados son concéntricos.
- Profundidad con **bordes de 1 px**, no con sombras. Solo los elementos flotantes (popover, ⌘K, tooltip) llevan sombra, de dos capas: `0 1px 2px rgb(0 0 0 / .2), 0 8px 24px rgb(0 0 0 / .24)`.

### Iconografía
- **Lucide** (`lucide-react`), trazo de 1,5 px, tamaño 16 px en la interfaz y 14 px en tablas.
- Escudos de los clubes como única imagen a color, a 16 o 20 px.
- Cero emojis.

### Motion
- Duraciones: hover y color 120 ms; popover y tooltip 150 ms; diálogo y ⌘K 200 ms; cambio de pestaña o panel 220 ms.
- Easings: entrada `cubic-bezier(0.16, 1, 0.3, 1)` (ease-out expo); salida `cubic-bezier(0.4, 0, 1, 1)` en 120 ms (las salidas son más rápidas que las entradas).
- Popovers que parten de su origen con `scale(0.97)` más opacidad.
- Los gráficos se dibujan una vez al cargar (400 ms máximo) y no se re-animan al filtrar: solo interpolan valores.
- Con `prefers-reduced-motion`, solo se anima la opacidad.
- Nunca se usa `transition: all`.

### Base técnica sugerida
**shadcn/ui** sobre **Radix** (accesibilidad y teclado ya resueltos), con los tokens de arriba sustituyendo el tema por defecto. Para la paleta de comandos, `cmdk`.

---

## 4. Navegación y layout

**Estructura de la aplicación (desktop ≥ 1024 px):**
```
┌ Sidebar 232px ┬───────────── Topbar 48px: breadcrumbs · ⌘K · tema ─┐
│ Logo          │                                                    │
│ Hoy           │   Contenido (máx. 1280px, alineado a la izquierda) │
│ Partidos      │                                                    │
│ Ligas  ▸ 5    │                                                    │
│ Equipos       │                                                    │
│ Modelo        │                                                    │
│ ── ── ──      │                                                    │
│ Metodología   │                                                    │
└───────────────┴────────────────────────────────────────────────────┘
```
- **Barra lateral** de 232 px con fondo sólido `surface-1` y borde derecho de 1 px. Se pliega a 56 px con `[`. Las ligas aparecen como lista con escudo. Sin CTAs ni bloques de "upgrade".
- **⌘K** como navegación global: busca equipo, partido ("bar rma") o liga, y lanza acciones ("Cambiar a modo claro", "Ir a calibración"). Cada resultado muestra su atajo.
- **Breadcrumbs** en la barra superior: `LaLiga / 2024-25 / J10 / Barcelona – Real Madrid`. Cada segmento abre un menú con sus hermanos (cambiar de jornada sin volver atrás).
- **Pestañas subrayadas** dentro de la ficha de partido: *Resumen · Modelo vs mercado · Tiros · Momentum · Jugadores*. Se sincronizan con la URL (`?tab=tiros`).
- **Vistas principales:**
  1. **Hoy / Próximos:** tabla de partidos agrupada por día con columnas *Hora · Partido · Modelo 1X2 (barra) · Mercado 1X2 (barra) · Mayor diferencia (pp) · Elo Δ*. Ordenable, con filtros como chips y fila clicable que abre la ficha.
  2. **Ficha de partido:** cabecera compacta (escudos, hora, estadio) y, a la izquierda, el bloque protagonista "Modelo 54 % · Mercado 47 % · +7 pp local". A la derecha, la explicación con los factores principales (forma, Elo, xG reciente).
  3. **Equipo:** forma de los últimos 10 partidos (W/D/L como cuadrados de 10 px con letra), Elo en el tiempo y xG a favor y en contra móvil.
  4. **Modelo:** curva de calibración, Brier y log-loss frente al mercado por liga y temporada, y una tabla de ROI simulado con advertencias.
- **Hoja lateral (sheet)** para la vista previa de un partido sin salir de la tabla: `Espacio` la abre y `Esc` la cierra.
- **Móvil:** la barra lateral pasa a barra inferior de 4 ítems. Las tablas se convierten en filas de dos líneas con las cifras a la derecha, sin apilar paneles infinitos.
- **No usar:** grid de 4 "KPI cards" como portada, hero dentro del dashboard ni una barra lateral flotante con bordes redondeados.

---

## 5. Reglas de visualización de datos de fútbol

**Generales (Tufte):** maximizar la proporción de tinta dedicada a datos, sin 3D, sin rejillas fuertes (rejilla horizontal de 1 px en `border` y nada en vertical), etiquetas directas sobre la serie en lugar de leyenda cuando quepa, y fuente de datos en `caption` bajo cada gráfico.

**Barra 1X2**
- Una barra horizontal apilada de 100 % con 8 px de alto en tabla y 24 px en ficha. Orden fijo: Local · Empate · Visitante. Colores de datos de la sección 3.
- Porcentajes encima o dentro solo si el segmento mide 32 px o más. Se redondean a enteros en la tabla y a un decimal en la ficha, y siempre suman 100.
- **Modelo frente a mercado:** dos barras apiladas una encima de otra con la misma escala, rotuladas "Modelo" y "Mercado (sin margen)". Debajo, una fila de diferencias en pp coloreada solo si |Δ| ≥ 3 pp.
- Alternativa en la ficha: un *dot plot* por resultado, con un punto sólido para el modelo, un aro gris para el mercado y una línea que los une. Es lo más legible para ver discrepancias.
- Muestra siempre que la probabilidad del mercado está normalizada (sin overround), con el método indicado en un tooltip (proporcional o Shin).

**Mapa de tiros (xG)**
- Medio campo vertical con la portería arriba y líneas del campo de 1 px en `border-strong` sobre `surface-1`. Nada de césped verde ni texturas.
- Área del marcador proporcional al xG (radio ∝ √xG), con una leyenda de tamaños de referencia de 0,05, 0,2 y 0,5.
- Gol = relleno sólido del color del equipo; no gol = aro hueco con opacidad 0,6. Así no se depende solo del color.
- Penaltis con forma distinta (cuadrado) o excluidos con un interruptor de "xG sin penaltis".
- Al pasar el cursor por un tiro: minuto, jugador, xG, parte del cuerpo y situación. Resalta también la fila en la lista de tiros vinculada.
- Resumen en la cabecera: `14 tiros · 1,87 xG · 2 goles`.
- Normaliza las coordenadas a un sistema único (0–100 o 120×80, estilo StatsBomb) antes de dibujar.

**Mapa de calor por jugador**
- Campo completo horizontal con dirección de ataque indicada (flecha pequeña en la cabecera, no sobre el campo).
- KDE o rejilla (bins 6×5 o hexbin). Escala **secuencial de una sola tonalidad** con transparencia en valores bajos. Nunca arcoíris ni jet.
- Las líneas del campo van por encima del calor para no perder la referencia.
- Indica minutos jugados y número de acciones: un mapa de calor con 15 acciones no es comparable con uno de 90.

**Momentum minuto a minuto**
- Barras divergentes por minuto alrededor de un eje central: local hacia arriba en su color y visitante hacia abajo en el suyo, como en FotMob y Sofascore.
- Marca descanso, goles (icono de 12 px en el eje) y tarjetas rojas.
- Suavizado opcional (media móvil de 3 a 5 min) con un control explícito.
- Explica la métrica en un tooltip "¿Qué es esto?", por ejemplo xT o xG ponderado por minuto. Bundesliga y Twenty3 documentan sus métodos, así que conviene citar el propio.

**Forma, Elo y series temporales**
- Forma: cuadrados W/D/L con letra (no solo color), del más reciente a la derecha.
- Elo: línea con área tenue, eje Y sin cero forzado, anotación en cambios de entrenador o fichajes clave si están disponibles y la media de la liga como línea de referencia gris.
- Evolución de la cuota: estilo Polymarket, con el mercado como línea con área y el modelo como línea horizontal o escalonada en el color de acento, más selector de rango.

**Calibración y evaluación**
- Diagrama de fiabilidad: eje X = probabilidad predicha (bins de 10 % o cuantiles), eje Y = frecuencia observada, diagonal de referencia gris discontinua.
- Modelo y mercado en el mismo gráfico con la codificación del principio 11. Bajo el gráfico, un histograma del número de casos por bin: los bins con pocos datos deben verse vacíos.
- Intervalos de confianza (bootstrap o Wilson) como barras verticales finas.
- Tabla de métricas: Brier, log-loss, RPS, n, por liga, con el mejor valor de cada fila en peso 600 (no en color).

---

## 6. Lista anti-slop y alternativas

| Evitar | Hacer en su lugar |
|---|---|
| Gradiente morado-azul, texto con gradiente | Fondo plano y un acento verde césped desaturado |
| Glassmorphism, `backdrop-blur` decorativo, brillos | Superficies opacas por niveles de luminosidad y bordes de 1 px |
| Emojis como iconos de sección (⚽📊🔥) | Lucide de 16 px o nada |
| Hero "Desbloquea el poder de la IA para tus apuestas" | Abrir directamente con la tabla de próximos partidos |
| Tarjetas con borde izquierdo de color | Color solo en el dato (barra 1X2, Δ pp) |
| Todo centrado | Alineación a la izquierda y cifras a la derecha |
| `rounded-2xl` con `shadow-lg` en todo | Radio de 6/8 px, borde y sombra solo en flotantes |
| Inter por defecto o Space Grotesk | Geist con Geist Mono (o Plex) y escala definida |
| Grid de 4 tarjetas KPI con flechas ▲ verdes | Una cifra protagonista contextualizada (modelo frente a mercado) |
| Métricas inventadas ("98 % de precisión", "+10.000 usuarios") | Métricas reales del backtest con n e intervalo |
| Etiquetas superiores en mayúsculas espaciadas en cada sección | Títulos en tono de frase y sin etiquetas superiores |
| Badges de colores en cada celda | Texto plano y badge solo para estados excepcionales (p. ej. "Sin cuotas") |
| Donuts y gráficos de relleno sin datos | Solo gráficos que responden una pregunta concreta |
| Puntos verdes de "Live" que laten | Estado en texto ("En juego · 67′") |
| Animaciones de entrada fade+slide en cada sección o hover que desplaza tarjetas | Sin animación al hacer scroll y hover que solo cambia el fondo |
| Barra lateral flotante redondeada con bloque de "Upgrade" | Barra lateral pegada al borde con borde de 1 px |
| Copys vacíos ("Insights accionables", "Datos de nueva generación") | Verbos y cifras: "El modelo da 7 pp más al local que el mercado" |
| Iconos genéricos de cohete, cerebro o rayo | Ningún icono decorativo |
| Mezcla de idiomas (Dashboard, Insights) | Todo en español: Panel, Partidos, Modelo, Calibración |
| Spinner a pantalla completa | Skeleton con la geometría final |
| Campo de fútbol con textura de césped o 3D | Campo plano con líneas finas |
| Palabras con "AI-powered" o ✨ | Explicar el método en la página Metodología |

---

## 7. Fuentes

- Vercel Web Interface Guidelines: https://github.com/vercel-labs/web-interface-guidelines
- Geist (tipografía y sistema): https://vercel.com/geist/typography · https://github.com/vercel/geist-font · https://vercel.com/font
- Linear, "How we redesigned the Linear UI": https://linear.app/now/how-we-redesigned-the-linear-ui
- Stripe, "Designing accessible color systems": https://stripe.com/blog/accessible-color-systems
- Rauno Freiberg, "Invisible details of interaction design": https://rauno.me/craft/interaction-design
- Emil Kowalski, "Great animations": https://emilkowal.ski/ui/great-animations
- Anthropic, skill frontend-design: https://github.com/anthropics/skills/tree/main/skills/frontend-design · https://skills.sh/anthropics/claude-code/frontend-design
- Uncodixfy (reglas anti "Codex UI"; revisar antes de instalar, tiene aviso de seguridad): https://github.com/cyxzdev/Uncodixfy · https://tessl.io/registry/skills/github/cyxzdev/Uncodixfy/uncodixfy/review
- Taste skill: https://www.ui-skills.com/skills/leonxlnx/taste-skill · Anti-AI-slop: https://www.skills.sh/lennney/skills/anti-ai-slop
- Design anti-patterns: https://tessl.io/registry/skills/github/Jamie-BitFlight/claude_skills/design-anti-patterns/review
- shadcn/ui: https://ui.shadcn.com · Radix: https://www.radix-ui.com · cmdk: https://cmdk.paco.me · Lucide: https://lucide.dev
- Refactoring UI: https://www.refactoringui.com · awesome-design-systems: https://github.com/alexpate/awesome-design-systems
- Tufte, *The Visual Display of Quantitative Information*: https://www.edwardtufte.com/book/the-visual-display-of-quantitative-information/
- Dribbble: https://dribbble.com/tags/web-design · https://dribbble.com/zenyvo · https://dribbble.com/beauvessen/collections/7754319-Ranking · https://dribbble.com/ugurcanbulut/collections/6057400-Football-Manager
- Mapa de xG (tamaño ∝ xG, relleno = gol): https://observablehq.com/@probberechts/xg-map
- mplsoccer (convenciones de campo): https://mplsoccer.readthedocs.io
- Momentum: https://aws.amazon.com/blogs/media/bundesliga-match-fact-match-momentum-revealing-the-games-invisible-pulse · https://twenty3.sport/?p=7943 · https://sofascore.com/news/?p=71696 · FotMob xG: https://www.fotmob.com/fa/topnews/3627-Live-xG-data-is-now-in-FotMob
- Opta Analyst predicciones: https://theanalyst.com/articles/opta-football-predictions · Win probability: https://www.statsperform.com/news/explained-what-is-win-probability-and-how-does-it-work
- Mercados de predicción (UI): https://humaninvariant.substack.com/p/novel-interface-designs-for-prediction · https://avark.agency/learn/prediction-market-design-patterns
- Referentes: https://linear.app · https://vercel.com · https://stripe.com · https://ramp.com · https://mercury.com · https://raycast.com · https://resend.com · https://posthog.com · https://attio.com · https://cal.com · https://supabase.com · https://www.fotmob.com · https://theanalyst.com · https://statsbomb.com · https://polymarket.com · https://kalshi.com
