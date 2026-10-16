<p align="center">
  <img src="web/public/favicon.svg" width="56" alt="Halfline">
</p>

<h1 align="center">Halfline</h1>

<p align="center">
  Probabilidades 1X2 para las cinco grandes ligas europeas, comparadas con las casas de apuestas y Polymarket.
</p>

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white">
  <img alt="React" src="https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black">
  <img alt="TypeScript" src="https://img.shields.io/badge/TypeScript-6-3178C6?logo=typescript&logoColor=white">
  <img alt="Tests" src="https://img.shields.io/badge/tests-pytest-0A9EDC?logo=pytest&logoColor=white">
</p>

---

Halfline calcula antes de cada partido la probabilidad de victoria local, empate y victoria visitante. Quita el margen de las cuotas para sacar la probabilidad implícita del mercado y la compara con modelos propios: Elo ajustado por xG, Dixon-Coles y metamodelos. Todo se evalúa fuera de muestra.

## Funcionalidades

- **Jornada:** próximos partidos con la probabilidad del modelo frente a la del mercado sin margen.
- **Ficha de partido:** mapa de tiros con xG, carrera de xG, momentum, alineaciones, mapas de calor y estadísticas avanzadas.
- **Ligas y equipos:** clasificación con goles esperados (xG) y puntos esperados (xPts), forma reciente, Elo y rendimiento subyacente.
- **Jugadores y estilos:** perfiles por rol con percentiles por 90 minutos, jugadores similares y mapa de estilos de juego.
- **Evaluación del modelo:** log-loss, Brier y RPS por liga, calibración y retorno simulado con intervalos de confianza.
- **Mercados:** margen de cada casa, sesgos del mercado y comparación con Polymarket.

## Resultados

Test fuera de muestra: temporadas 2025/26 y 2026/27, 2.049 partidos. Menos es mejor.

| Modelo | Log-loss |
|---|---|
| Mercado de cierre (sin margen) | 0,975 |
| Mercado pre-cierre (sin margen) | 0,976 |
| Elo ajustado por xG | 0,993 |
| Frecuencias históricas | 1,071 |

El detalle está en [`docs/modelos.md`](docs/modelos.md) y [`docs/sesgos_mercado.md`](docs/sesgos_mercado.md).

## Arquitectura

```
futdata/             Ingesta, limpieza, variables, modelos y API
├── football_data    Resultados y cuotas de cierre
├── espn             Estadísticas, alineaciones y calendario
├── understat        xG por partido
├── pitchapi         Tiros con coordenadas, momentum y mapas de calor
├── transfermarkt    Valores de mercado de las plantillas
├── polymarket       Precios del mercado de predicción
├── features         Variables previas al partido, sin fuga de información
├── models/          Elo, goles, eliminación de margen, evaluación y sesgos
└── api              API Flask de solo lectura
web/                 Frontend en React + TypeScript + Vite
tests/               Tests con pytest
docs/                Notas técnicas de datos, modelos y diseño
```

## Puesta en marcha

Requisitos: Python 3.12 o superior y Node 22 o superior.

```bash
pip install -r requirements.txt
npm install --prefix web
```

Datos (no se versionan):

```bash
python -m futdata download          # fuentes crudas: football_data, espn, understat, transfermarkt, pitchapi
python -m futdata.polymarket        # precios de Polymarket
python -m futdata.features          # tabla de variables
python -m futdata.models.evaluate   # entrenamiento y evaluación
```

PitchAPI necesita una clave en `.env`:

```bash
PITCHAPI_KEY=tu_clave
```

Desarrollo:

```bash
./scripts/dev.sh                    # API en :8000 y web en http://localhost:5173
```

Tests:

```bash
python -m pytest
```

## API

| Endpoint | Descripción |
|---|---|
| `GET /api/meta` | Cobertura y fecha de los datos |
| `GET /api/upcoming?days=` | Próximos partidos con probabilidades |
| `GET /api/matches?league=&season=&team=&limit=` | Partidos jugados |
| `GET /api/matches/<match_id>` | Ficha completa de un partido |
| `GET /api/leagues/<league>/table?season=` | Clasificación con xG y xPts |
| `GET /api/teams/<league>/<team>?season=` | Página de equipo |
| `GET /api/teams` | Equipos disponibles |

## Stack

Python · pandas · NumPy · SciPy · scikit-learn · Flask · React · TypeScript · Vite · Tailwind CSS · d3 · Motion
