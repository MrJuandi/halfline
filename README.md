# Predicción 1X2 en fútbol con Machine Learning

TFG sobre modelos de machine learning que estiman, antes de cada partido, la probabilidad de **victoria local, empate y victoria visitante**. El trabajo estudia si esas probabilidades son fiables y las compara con las del mercado de apuestas.

## Motivación

El fútbol es difícil de predecir: hay pocos goles, mucho azar y muchos empates. Queremos saber hasta dónde llega el ML con datos públicos y qué distancia hay con las casas de apuestas.

## Objetivo

Una aplicación web que muestre las probabilidades 1X2 de cada partido, cómo de fiables son y cómo se comparan con el mercado.

## Datos

- Resultados y estadísticas de partidos de las 5 grandes ligas europeas
- Cuotas de casas de apuestas y precios de Polymarket
- Fuente principal: [Football-Data.co.uk](https://www.football-data.co.uk/data.php)

## Modelo

Clasificación en tres clases (1, X, 2) con **Gradient Boosting**. Se compara con modelos más simples (Elo, Poisson, regresión logística) y con el mercado. Después se calibran las probabilidades.

## Pipeline

```
Datos → Limpieza → Variables → Modelo ML → Evaluación → App
```

## Tecnologías

Python · pandas · numpy · scikit-learn · matplotlib
