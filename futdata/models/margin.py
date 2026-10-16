"""Quitar el margen de las cuotas: probabilidades que suman 1 a partir de cuotas (n, k).

- proportional(): divide 1/cuota entre la suma. Deja un sesgo favorito-longshot (las sorpresas
  quedan sobrevaloradas), ver docs/sesgos_mercado.md.
- shin(): Shin (1993; Štrumbelj, 2014). Atribuye el margen a apostantes informados.
- power(): p_i = (1/cuota_i)^k con k tal que suman 1. Es el mejor calibrado en nuestros datos y
  el que usa el proyecto (fair()).
"""
from __future__ import annotations

import numpy as np


def _bisect(f, lo: np.ndarray, hi: np.ndarray, iters: int = 80) -> np.ndarray:
    """Raíz de f (decreciente) en [lo, hi], fila a fila."""
    for _ in range(iters):
        mid = (lo + hi) / 2
        pos = f(mid) > 0
        lo, hi = np.where(pos, mid, lo), np.where(pos, hi, mid)
    return (lo + hi) / 2


def proportional(odds: np.ndarray) -> np.ndarray:
    q = 1 / odds
    return q / q.sum(1, keepdims=True)


def shin(odds: np.ndarray) -> np.ndarray:
    """Método de Shin (1993; Štrumbelj, 2014): el margen se atribuye a apostantes informados,
    así que se quita más a las sorpresas que a los favoritos. Sin margen positivo, proporcional."""
    q = 1 / odds
    Q = q.sum(1, keepdims=True)

    def probs(z):
        z = z[:, None]
        return (np.sqrt(z ** 2 + 4 * (1 - z) * q ** 2 / Q) - z) / (2 * (1 - z))

    n = len(q)
    z = _bisect(lambda z: probs(z).sum(1) - 1, np.zeros(n), np.full(n, 0.5))
    p = probs(z)
    return np.where(Q > 1, p / p.sum(1, keepdims=True), q / Q)


def power(odds: np.ndarray) -> np.ndarray:
    """p_i = q_i^k con k tal que suman 1."""
    q = 1 / odds
    n = len(q)
    k = _bisect(lambda k: (q ** k[:, None]).sum(1) - 1, np.full(n, 0.2), np.full(n, 5.0))
    p = q ** k[:, None]
    return p / p.sum(1, keepdims=True)


def fair(odds: np.ndarray) -> np.ndarray:
    """Probabilidades sin margen del proyecto (potencia). NaN en la fila si falta alguna cuota."""
    odds = np.asarray(odds, dtype=float)
    ok = (odds > 1).all(1)
    out = np.full(odds.shape, np.nan)
    if ok.any():
        out[ok] = power(odds[ok])
    return out
