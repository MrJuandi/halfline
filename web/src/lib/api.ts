import { useEffect, useState } from 'react'

/* Tipos de la API (futdata/api.py). Las probabilidades van de 0 a 1. */

export type LeagueCode = 'SP1' | 'E0' | 'I1' | 'D1' | 'F1'
export type Probs = { home: number; draw: number; away: number }
export type Outcome = 'W' | 'D' | 'L'

export type Meta = {
  generated_at: string
  data_through: string
  counts: { matches: number; teams: number; shots: number }
  leagues: { code: LeagueCode; name: string; seasons: number[] }[]
  teams: Record<string, { name: string; crest: string | null; color?: string }>
}

export type TeamRef = { league: LeagueCode; team: string; seasons: number[] }

export type MatchSummary = {
  match_id: string
  league: LeagueCode
  season: number
  kickoff: string | null
  home: string
  away: string
  home_goals: number
  away_goals: number
  home_xg: number | null
  away_xg: number | null
  market: Probs | null
  has_heatmaps: boolean
}

export type TableRow = {
  pos: number
  team: string
  played: number
  won: number
  drawn: number
  lost: number
  gf: number
  ga: number
  gd: number
  pts: number
  xg_for: number
  xg_against: number
  xg_diff: number
  xpts: number
  form: Outcome[]
}

export type Side = 'home' | 'away'
export type Shot = {
  side: Side
  player: string
  minute: number
  x: number
  y: number
  xg: number
  xgot: number | null
  outcome: 'goal' | 'saved' | 'miss' | 'post' | 'blocked' | 'other'
  situation: string
  body: string
}
export type MatchEvent = {
  type: 'goal' | 'yellowcard' | 'redcard' | 'substitution' | string
  minute: number
  added: number
  side: Side
  player: string | null
  detail: string | null
  own_goal: boolean
  penalty: boolean
}
export type Cells = [number, number, number][]
export type LineupPlayer = { name: string; number: string | number | null; x: number; y: number; captain: boolean }
export type TeamForm = {
  elo: number | null
  rest_days: number | null
  form: { xg_for: number | null; xg_against: number | null; goals_for: number | null; goals_against: number | null; points: number | null }
  last5: Outcome[]
}
export type MatchDetail = {
  match: MatchSummary
  pre_match: {
    home: TeamForm
    away: TeamForm
    /** pre/close sin margen (método de potencia); odds son las cuotas medias pre-cierre tal cual. */
    market: { pre: Probs | null; close: Probs | null; overround?: number | null; odds?: Probs | null }
    /** Probabilidades fuera de muestra del modelo propio que enseña la web. */
    model?: { name: string; probs: Probs } | null
  }
  stats: { key: string; label: string; group: string; home: number | null; away: number | null }[]
  shots: Shot[]
  momentum: { minute: number; value: number }[]
  events: MatchEvent[]
  lineups: { home: { formation: string; coach: string | null; starters: LineupPlayer[] }; away: { formation: string; coach: string | null; starters: LineupPlayer[] } } | null
  heatmaps: {
    grid: { length: number; width: number }
    teams: { home: Cells; away: Cells }
    players: { name: string; number: string | number | null; side: Side; actions: number; cells: Cells }[]
  } | null
  advanced: Record<Side, Record<string, number | null>> | null
}

export type TeamPage = {
  team: string
  league: LeagueCode
  season: number
  matches: { match_id: string; kickoff: string; opponent: string; venue: 'H' | 'A'; gf: number; ga: number; xg_for: number | null; xg_against: number | null; result: Outcome; elo_before: number | null }[]
  series: { kickoff: string; ewm_xg_for: number | null; ewm_xg_against: number | null; elo: number | null }[]
  summary: { played: number; pts: number; gf: number; ga: number; xg_for: number; xg_against: number }
}

export type Upcoming = {
  league: LeagueCode
  kickoff: string
  home: string
  away: string
  espn_id: string
  market: Probs | null
  model: Probs | null
}

/* ---------------------------------------------------------------- fetch con caché */

const cache = new Map<string, unknown>()
const inflight = new Map<string, Promise<unknown>>()

export function fetchJson<T>(path: string): Promise<T> {
  if (cache.has(path)) return Promise.resolve(cache.get(path) as T)
  if (!inflight.has(path)) {
    inflight.set(
      path,
      fetch(path)
        .then(async (r) => {
          if (!r.ok) throw new Error(r.status === 404 ? 'No encontrado' : `Error ${r.status} al pedir ${path}`)
          const data = await r.json()
          cache.set(path, data)
          return data
        })
        .finally(() => inflight.delete(path)),
    )
  }
  return inflight.get(path) as Promise<T>
}

export function prefetch(path: string) {
  fetchJson(path).catch(() => {})
}

/** Casas de apuestas frente a Polymarket en los mismos partidos (/api/markets). */
export type Markets = {
  n: number
  edges: number[]
  books: { mean: number; hist: number[] }
  polymarket: { mean: number; hist: number[] }
  all_books_mean: number
  all_books_n: number
  accuracy: { source: string; n: number; logloss: number }[]
}

/** Evaluación real fuera de muestra (/api/model). */
export type Metrics = { logloss: number; brier: number; rps: number }
export type ModelEval = {
  model: string
  market: string
  seasons: number[]
  ranking: { model: string; n: number; logloss: number; rps: number; brier: number; vs_market: number; ci: [number, number] }[]
  leagues: { league: LeagueCode | null; n: number; model: Metrics; market: Metrics }[]
  calibration: { model: { p: number; freq: number; n: number; lo: number; hi: number }[]; market: { p: number; freq: number; n: number; lo: number; hi: number }[] }
  bets: { model: string; bets: number; roi: number; roi_ci: [number, number] }[]
}

export type Loadable<T> = { data: T | undefined; error: string | null; loading: boolean }

export function useApi<T>(path: string | null): Loadable<T> {
  const [state, setState] = useState<Loadable<T>>(() => ({
    data: path && cache.has(path) ? (cache.get(path) as T) : undefined,
    error: null,
    loading: !!path && !cache.has(path),
  }))
  useEffect(() => {
    if (!path) return
    let alive = true
    if (cache.has(path)) {
      setState({ data: cache.get(path) as T, error: null, loading: false })
      return
    }
    setState((s) => ({ data: s.data, error: null, loading: true }))
    fetchJson<T>(path)
      .then((data) => alive && setState({ data, error: null, loading: false }))
      .catch((e: Error) => alive && setState({ data: undefined, error: e.message, loading: false }))
    return () => {
      alive = false
    }
  }, [path])
  return state
}

export const api = {
  meta: '/api/meta',
  teams: '/api/teams',
  table: (league: string, season: number) => `/api/leagues/${league}/table?season=${season}`,
  matches: (q: { league?: string; season?: number; team?: string; limit?: number }) => {
    const p = new URLSearchParams()
    Object.entries(q).forEach(([k, v]) => v !== undefined && v !== '' && p.set(k, String(v)))
    return `/api/matches?${p}`
  },
  match: (id: string) => `/api/matches/${encodeURIComponent(id)}`,
  team: (league: string, team: string, season?: number) =>
    `/api/teams/${league}/${encodeURIComponent(team)}${season ? `?season=${season}` : ''}`,
  markets: '/api/markets',
  model: '/api/model',
  upcoming: (days = 21) => `/api/upcoming?days=${days}`,
  styles: '/api/styles',
}

/** Nombre completo y escudo de un equipo a partir de su nombre canónico (Football-Data). */
export function useTeams() {
  const { data } = useApi<Meta>(api.meta)
  const teams = data?.teams
  return {
    name: (t: string) => teams?.[t]?.name ?? t,
    crest: (t: string) => teams?.[t]?.crest ?? null,
  }
}

/** Versión síncrona de useTeams().name: la app no muestra páginas hasta tener /api/meta. */
export function teamName(t: string): string {
  const meta = cache.get(api.meta) as Meta | undefined
  return meta?.teams?.[t]?.name ?? t
}

/* ---------------------------------------------------------------- analizador de equipo */

export type Role = 'POR' | 'DEF' | 'MED' | 'DEL'
export type Impact = {
  on_minutes: number
  off_minutes: number
  xgf90_on: number
  xga90_on: number
  xgf90_off: number
  xga90_off: number
  xgd90_on: number
  xgd90_off: number
  delta: number
  goals_on: [number, number]
}
export type SquadPlayer = {
  id: string
  name: string
  photo: string | null
  number: string | number | null
  role: Role | null
  apps: number
  starts: number
  minutes: number
  goals?: number
  assists?: number
  xg?: number
  npxg?: number
  xa?: number
  shots?: number
  shots_on_target?: number
  chances?: number
  touches?: number
  box_touches?: number
  dribbles?: number
  tackles?: number
  interceptions?: number
  recoveries?: number
  duels_won?: number
  duels_lost?: number
  final_third_passes?: number
  saves?: number
  goals_prevented?: number
  goals_conceded?: number
  rating: number | null
  avg_x: number | null
  avg_y: number | null
  impact: Impact | null
}
export type SeasonShot = { x: number; y: number; xg: number; goal: boolean; player: string; minute: number; match_id: string }
export type TeamAnalysis = {
  team: string
  league: LeagueCode
  season: number
  matches: number
  squad: SquadPlayer[]
  typical_xi: { id: string; name: string; number: string | number | null; x: number; y: number; starts: number; slot_starts: number; role: Role; photo: string | null }[]
  typical_formation: string | null
  formations: { formation: string; matches: number; ppg: number; w: number; d: number; l: number }[]
  shots: { for: SeasonShot[]; against: SeasonShot[] }
  goals_by_15: { for: number[]; against: number[] }
  totals: { min: number; xgf: number; xga: number; gf: number; ga: number }
  style: { key: string; label: string; value: number; pct: number; league_avg: number; rank: number; teams: number }[]
  impact_min_minutes: number
}

export const analysisUrl = (league: string, team: string, season?: number) =>
  `/api/analysis/${league}/${encodeURIComponent(team)}${season ? `?season=${season}` : ''}`

/* ---------------------------------------------------------------- estilos de juego */

export type ArchetypeKey = 'dominio' | 'control' | 'directo' | 'aereo' | 'sufridor' | 'equilibrio'
export type StyleTeam = {
  league: LeagueCode
  season: number
  team: string
  matches: number
  pc1: number
  pc2: number
  pc3: number
  archetype: ArchetypeKey
  values: Record<string, number>
  z: Record<string, number>
  similar: { team: string; league: LeagueCode; distance: number }[]
}
export type Styles = {
  n: number
  explained: number[]
  features: { key: string; label: string; description: string }[]
  axes: { name: string; explained: number; positive: string[]; negative: string[]; loadings: Record<string, number> }[]
  archetypes: {
    key: ArchetypeKey
    name: string
    description: string
    color: string
    size: number
    traits_high: string[]
    traits_low: string[]
    centroid: Record<string, number>
    typical: { team: string; league: LeagueCode; season: number }[]
    pc: [number, number]
  }[]
  teams: StyleTeam[]
  movers: { league: LeagueCode; team: string; from: number; to: number; distance: number; path: [number, number][]; archetypes: [ArchetypeKey, ArchetypeKey] }[]
  leagues: { league: LeagueCode; pc1: number; pc2: number }[]
  current: StyleCurrent[]
  window: number
}
/** Estado actual de un equipo: últimos `window` partidos, proyectados en el mismo mapa. */
export type StyleCurrent = StyleTeam & {
  this_season: number
  from: string
  to: string
  short_sample: boolean
  prev: { pc1: number; pc2: number; archetype: ArchetypeKey; season: number } | null
}

export function teamCrest(t: string): string | null {
  const meta = cache.get(api.meta) as Meta | undefined
  return meta?.teams?.[t]?.crest ?? null
}

/* ---------------------------------------------------------------- perfiles de jugador */

export type PlayerRole = { key: string; name: string; description: string; color: string; size: number; pc: [number, number]; traits_high: string[] }
export type PlayerDot = { player_id: string; name: string; photo: string | null; team: string; league: LeagueCode; season: number; minutes: number; goals: number; assists: number; pc1: number; pc2: number; role: string }
export type PlayerMap = { season: number | 'now'; seasons: number[]; roles: { n: number; explained: number[]; roles: PlayerRole[]; axes: { name: string }[] }; players: PlayerDot[] }
export type PlayerProfile = {
  window: 'now' | 'season'
  window_from: string | null
  window_to: string | null
  this_season: number | null
  short_sample: boolean
  has_now: boolean
  seasons: number[]
  player_id: string
  name: string
  photo: string | null
  team: string
  league: LeagueCode
  season: number
  minutes: number
  goals: number
  assists: number
  xg: number
  xa: number
  rating: number | null
  role: string
  pc: [number, number]
  features: { key: string; label: string; value: number; z: number; pct_role: number }[]
  history: { season: number; team: string; league: LeagueCode; role: string; minutes: number; pc: [number, number] }[]
  similar: { player_id: string; name: string; photo: string | null; team: string; league: LeagueCode; season: number; role: string; similarity: number }[]
}
export const playersUrl = (season?: number | 'now', league?: string) => `/api/players?${new URLSearchParams({ ...(season ? { season: String(season) } : {}), ...(league && league !== 'all' ? { league } : {}) })}`
export const playerUrl = (id: string, season?: number | 'now') => `/api/players/${id}${season ? `?season=${season}` : ''}`

export function teamColor(t: string): string | null {
  const meta = cache.get(api.meta) as Meta | undefined
  return meta?.teams?.[t]?.color ?? null
}
