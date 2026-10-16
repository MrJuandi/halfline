import type { Probs } from './api'

/* Datos de EJEMPLO mientras no exista el modelo. Todo lo que sale de aquí se muestra con la
   etiqueta «Ejemplo» en la interfaz. Son deterministas (mismo partido, mismo número). */

function hash(s: string): number {
  let h = 2166136261
  for (let i = 0; i < s.length; i++) h = Math.imul(h ^ s.charCodeAt(i), 16777619)
  return (h >>> 0) / 4294967295
}

/** Probabilidad de ejemplo: el mercado (o un reparto típico) desplazado unos puntos. */
export function exampleModel(key: string, market: Probs | null): Probs {
  const base = market ?? { home: 0.44, draw: 0.26, away: 0.3 }
  const shift = (hash(key) - 0.5) * 0.16
  const home = Math.min(0.85, Math.max(0.08, base.home + shift))
  const away = Math.min(0.85, Math.max(0.06, base.away - shift * 0.7))
  const draw = Math.max(0.12, 1 - home - away)
  const s = home + draw + away
  return { home: home / s, draw: draw / s, away: away / s }
}

/** Diferencia con mayor valor absoluto entre modelo y mercado. */
export function biggestEdge(model: Probs, market: Probs): { side: keyof Probs; delta: number } {
  const keys: (keyof Probs)[] = ['home', 'draw', 'away']
  return keys
    .map((k) => ({ side: k, delta: model[k] - market[k] }))
    .reduce((a, b) => (Math.abs(b.delta) > Math.abs(a.delta) ? b : a))
}
