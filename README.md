<p align="center">
  <img src="web/public/favicon.svg" width="64" alt="Halfline">
</p>

<h1 align="center">Halfline</h1>

<p align="center"><b>Quita el margen. Mira el partido.</b><br>
Probabilidades 1X2 de fútbol con machine learning, comparadas con las casas de apuestas y Polymarket.</p>

---

Trabajo de Fin de Grado. Halfline estima, antes de cada partido de las cinco grandes ligas europeas, la probabilidad de **victoria local, empate y victoria visitante**. Después le quita a las cuotas el margen que cobran las casas y compara lo que queda con un modelo propio y con Polymarket.

El nombre viene de la *halfway line*, la línea de medio campo. Es el punto justo entre local y visitante, y también la *line* de las apuestas.

## Qué hay dentro

| Carpeta | Contenido |
|---|---|
| `futdata/` | Descarga y limpieza de datos (Football-Data, Understat, ESPN, Transfermarkt, Polymarket), variables, modelos y la API Flask |
| `futdata/models/` | Elo, Poisson y goles, quitar el margen, sesgos del mercado, evaluación y comparación con Polymarket |
| `web/` | Aplicación React + TypeScript + Vite |
| `docs/` | Notas de datos, modelos, sesgos del mercado y diseño |
| `tests/` | Tests con pytest |

## Pipeline

```
Datos → Limpieza → Variables → Modelo → Quitar margen → Evaluación → App
```

## Arrancar en local

```bash
pip install -r requirements.txt
npm install --prefix web
./scripts/dev.sh        # API en :8000 y web en http://localhost:5173
```

Los datos (`data/`) no están en el repositorio por su tamaño. Se regeneran con `python -m futdata download`. La clave de PitchAPI va en `.env` como `PITCHAPI_KEY`.

## Identidad

| Rol | Oscuro | Claro |
|---|---|---|
| Fondo | `#0c0d0f` | `#f3f3f1` |
| Acento (ventaja, modelo) | `#4cc38a` | `#18794e` |
| Local | `#5b9bf0` | `#2563c9` |
| Empate | `#8e9096` | `#7a7c83` |
| Visitante | `#e5a54b` | `#b7741a` |

Tipografía: Geist. Logo: círculo central cortado por la línea de medio campo.

## Tecnologías

Python · pandas · numpy · scikit-learn · scipy · Flask · React · TypeScript · Vite · Tailwind · d3
