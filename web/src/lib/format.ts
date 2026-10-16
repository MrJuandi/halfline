/* Formato español: coma decimal, porcentajes con espacio fino, horas en Europe/Madrid. */

const TZ = 'Europe/Madrid'
const NBSP = ' '

export const LEAGUES = {
  SP1: { name: 'LaLiga', short: 'ESP', country: 'España' },
  E0: { name: 'Premier League', short: 'ENG', country: 'Inglaterra' },
  I1: { name: 'Serie A', short: 'ITA', country: 'Italia' },
  D1: { name: 'Bundesliga', short: 'GER', country: 'Alemania' },
  F1: { name: 'Ligue 1', short: 'FRA', country: 'Francia' },
} as const
export const LEAGUE_ORDER = ['SP1', 'E0', 'I1', 'D1', 'F1'] as const

export const seasonLabel = (s: number) => `${s}/${String((s + 1) % 100).padStart(2, '0')}`

export function num(v: number | null | undefined, digits = 2): string {
  if (v === null || v === undefined || Number.isNaN(v)) return '–'
  return v.toLocaleString('es-ES', { minimumFractionDigits: digits, maximumFractionDigits: digits })
}

export function int(v: number | null | undefined): string {
  if (v === null || v === undefined || Number.isNaN(v)) return '–'
  // useGrouping 'always': separador de miles también con 4 cifras (9.205), coherente en columnas
  return Math.round(v).toLocaleString('es-ES', { useGrouping: 'always' } as Intl.NumberFormatOptions)
}

export function pct(p: number | null | undefined, digits = 0): string {
  if (p === null || p === undefined || Number.isNaN(p)) return '–'
  return `${(p * 100).toLocaleString('es-ES', { minimumFractionDigits: digits, maximumFractionDigits: digits })}${NBSP}%`
}

/** Diferencia en puntos porcentuales con signo explícito: +7 pp, −3 pp. */
export function pp(d: number, digits = 0): string {
  const v = d * 100
  const s = Math.abs(v).toLocaleString('es-ES', { minimumFractionDigits: digits, maximumFractionDigits: digits })
  return `${v > 0 ? '+' : v < 0 ? '−' : '±'}${s}${NBSP}pp`
}

export function signed(v: number, digits = 2): string {
  const s = Math.abs(v).toLocaleString('es-ES', { minimumFractionDigits: digits, maximumFractionDigits: digits })
  return `${v > 0 ? '+' : v < 0 ? '−' : '±'}${s}`
}

const dayFmt = new Intl.DateTimeFormat('es-ES', { timeZone: TZ, weekday: 'short', day: 'numeric', month: 'short' })
const longDayFmt = new Intl.DateTimeFormat('es-ES', { timeZone: TZ, weekday: 'long', day: 'numeric', month: 'long' })
const timeFmt = new Intl.DateTimeFormat('es-ES', { timeZone: TZ, hour: '2-digit', minute: '2-digit' })
const dateFmt = new Intl.DateTimeFormat('es-ES', { timeZone: TZ, day: 'numeric', month: 'short', year: 'numeric' })
const keyFmt = new Intl.DateTimeFormat('en-CA', { timeZone: TZ, year: 'numeric', month: '2-digit', day: '2-digit' })

const clean = (s: string) => s.replace(/\./g, '')
export const day = (iso: string | null) => (iso ? clean(dayFmt.format(new Date(iso))) : '–')
export const longDay = (iso: string) => {
  const s = longDayFmt.format(new Date(iso))
  return s.charAt(0).toUpperCase() + s.slice(1)
}
export const time = (iso: string | null) => (iso ? timeFmt.format(new Date(iso)) : '–')
export const date = (iso: string | null) => (iso ? clean(dateFmt.format(new Date(iso))) : '–')
export const dayKey = (iso: string) => keyFmt.format(new Date(iso))
export const dayTime = (iso: string) => `${day(iso)} · ${time(iso)}`

export function relativeDays(iso: string): string {
  const today = dayKey(new Date().toISOString())
  const diff = Math.round((Date.parse(dayKey(iso)) - Date.parse(today)) / 86_400_000)
  if (diff === 0) return 'Hoy'
  if (diff === 1) return 'Mañana'
  if (diff === -1) return 'Ayer'
  return longDay(iso)
}

/** Iniciales para el distintivo de un equipo cuando no hay escudo. */
export function initials(team: string): string {
  const words = team.replace(/[^A-Za-zÀ-ÿ ]/g, ' ').split(/\s+/).filter(Boolean)
  if (words.length === 1) return words[0].slice(0, 3).toUpperCase()
  return words.slice(0, 3).map((w) => w[0]).join('').toUpperCase()
}

export const slug = (team: string) => encodeURIComponent(team)

/** Separa etiquetas que se pisarían: si dos están a menos de `gap` px en vertical y se solapan
 *  en horizontal (ancho estimado por número de letras), baja la segunda. */
export function declutter<T extends { x: number; y: number; text: string }>(labels: T[], gap = 15, charW = 7.2): (T & { ly: number })[] {
  const placed: (T & { ly: number })[] = []
  for (const l of [...labels].sort((a, b) => a.y - b.y)) {
    let ly = l.y
    const w = l.text.length * charW
    for (let moved = true; moved; ) {
      moved = false
      for (const p of placed) {
        const pw = p.text.length * charW
        if (Math.abs(p.x - l.x) < (w + pw) / 2 + 6 && Math.abs(p.ly - ly) < gap) {
          ly = p.ly + gap
          moved = true
        }
      }
    }
    placed.push({ ...l, ly })
  }
  return placed
}
