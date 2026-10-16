import { Search } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { PageHeader, useCrumbs } from '../components/shell'
import { cx, ErrorState, Kbd, Panel, ProbBar, Segmented, Select, Skeleton, Stat, TeamBadge } from '../components/ui'
import { api, prefetch, useApi, type MatchSummary, type Meta, teamName as tn } from '../lib/api'
import { day, LEAGUE_ORDER, LEAGUES, num, pct, seasonLabel, time } from '../lib/format'

const PAGE = 80

/** Resumen de la selección: cuánto acertó el favorito del mercado y la mayor sorpresa. */
function Summary({ rows }: { rows: MatchSummary[] }) {
  const priced = rows.filter((m) => m.market)
  const favWon = priced.filter((m) => {
    const p = m.market!
    const fav = p.home >= p.away && p.home >= p.draw ? 'home' : p.away >= p.draw ? 'away' : 'draw'
    const res = m.home_goals > m.away_goals ? 'home' : m.home_goals === m.away_goals ? 'draw' : 'away'
    return fav === res
  }).length
  const draws = rows.filter((m) => m.home_goals === m.away_goals).length
  const upset = priced.reduce<MatchSummary | null>((best, m) => (best === null || (marketOnResult(m) ?? 1) < (marketOnResult(best) ?? 1) ? m : best), null)
  const withXg = rows.filter((m) => m.home_xg !== null)
  const xg = withXg.reduce((a, m) => a + (m.home_xg ?? 0) + (m.away_xg ?? 0), 0) / Math.max(withXg.length, 1)
  const goals = rows.reduce((a, m) => a + m.home_goals + m.away_goals, 0) / Math.max(rows.length, 1)
  return (
    <div className="mb-6 grid grid-cols-2 gap-3 lg:grid-cols-4">
      <Stat label="Ganó el favorito" value={pct(favWon / Math.max(priced.length, 1))} sub={`${favWon} de ${priced.length} partidos con cuotas`} />
      <Stat label="Empates" value={pct(draws / Math.max(rows.length, 1))} sub={`${draws} partidos`} />
      <Stat label="Goles por partido" value={num(goals)} sub={`xG ${num(xg)} por partido`} />
      {upset ? (
        <Link to={`/partidos/${upset.match_id}`} className="rounded-panel transition-transform active:scale-[0.99]">
          <Stat
            label="La mayor sorpresa"
            tone="neg"
            value={pct(marketOnResult(upset))}
            sub={`${tn(upset.home)} ${upset.home_goals}–${upset.away_goals} ${tn(upset.away)}`}
          />
        </Link>
      ) : (
        <Stat label="La mayor sorpresa" value="–" />
      )}
    </div>
  )
}

/** ¿Ganó el favorito del mercado? Devuelve la probabilidad que el mercado dio al resultado final. */
function marketOnResult(m: MatchSummary) {
  if (!m.market) return null
  const r = m.home_goals > m.away_goals ? 'home' : m.home_goals === m.away_goals ? 'draw' : 'away'
  return m.market[r]
}

export default function Matches() {
  const [params, setParams] = useSearchParams()
  const navigate = useNavigate()
  const { data: meta } = useApi<Meta>(api.meta)
  const seasons = meta?.leagues[0]?.seasons ?? []
  const league = params.get('liga') ?? 'all'
  const season = Number(params.get('temporada')) || seasons.at(-1)
  const [query, setQuery] = useState(params.get('q') ?? '')
  const [limit, setLimit] = useState(PAGE)
  const [cursor, setCursor] = useState(-1)
  const listRef = useRef<HTMLDivElement>(null)

  const { data, error, loading } = useApi<MatchSummary[]>(
    season ? api.matches({ league: league === 'all' ? undefined : league, season }) : null,
  )
  useCrumbs([{ label: 'Partidos' }])

  const set = (k: string, v: string | null) => {
    const p = new URLSearchParams(params)
    if (v === null || v === '') p.delete(k)
    else p.set(k, v)
    setParams(p, { replace: true })
    setLimit(PAGE)
    setCursor(-1)
  }

  const rows = useMemo(() => {
    const q = query.trim().toLowerCase().normalize('NFD').replace(/\p{Diacritic}/gu, '')
    if (!data) return []
    if (!q) return data
    return data.filter((m) => `${m.home} ${m.away}`.toLowerCase().normalize('NFD').replace(/\p{Diacritic}/gu, '').includes(q))
  }, [data, query])

  // J / K para moverse, Enter para abrir
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.target as HTMLElement)?.closest('input, textarea') || e.metaKey || e.ctrlKey) return
      if (e.key === 'j' || e.key === 'k') {
        e.preventDefault()
        setCursor((c) => Math.max(0, Math.min(Math.min(rows.length, limit) - 1, c + (e.key === 'j' ? 1 : -1))))
      } else if (e.key === 'Enter' && cursor >= 0 && rows[cursor]) {
        navigate(`/partidos/${rows[cursor].match_id}`)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [rows, cursor, limit, navigate])

  useEffect(() => {
    if (cursor < 0) return
    const el = listRef.current?.querySelector<HTMLElement>(`[data-row="${cursor}"]`)
    el?.scrollIntoView({ block: 'nearest' })
    if (rows[cursor]) prefetch(api.match(rows[cursor].match_id))
  }, [cursor, rows])

  return (
    <>
      <PageHeader
        title="Partidos"
        sub={data ? `${rows.length.toLocaleString('es-ES')} partidos · ${season ? seasonLabel(season) : ''}` : ' '}
        actions={
          <span className="hidden items-center gap-1.5 text-caption text-subtle lg:flex">
            <Kbd>J</Kbd>
            <Kbd>K</Kbd> moverse <Kbd>↵</Kbd> abrir
          </span>
        }
      />
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <Segmented
          id="league"
          value={league}
          onChange={(v) => set('liga', v === 'all' ? null : v)}
          options={[{ value: 'all', label: 'Todas' }, ...LEAGUE_ORDER.map((c) => ({ value: c, label: LEAGUES[c].short }))]}
        />
        <Select
          label="Temporada"
          value={season}
          onChange={(v) => set('temporada', v)}
          options={[...seasons].reverse().map((s) => ({ value: s, label: seasonLabel(s) }))}
        />
        <label className="flex h-9 min-w-56 flex-1 items-center gap-2 rounded-ctl bg-surface-1 px-3 text-label transition-colors focus-within:bg-surface-3 sm:flex-none">
          <Search size={14} className="text-subtle" />
          <input
            value={query}
            onChange={(e) => {
              setQuery(e.target.value)
              set('q', e.target.value)
            }}
            placeholder="Filtrar por equipo"
            className="w-full bg-transparent outline-none placeholder:text-subtle"
          />
        </label>
      </div>

      {error && <ErrorState message="No se pudieron cargar los partidos." />}
      {data && rows.length > 0 && <Summary rows={rows} />}
      <Panel className="overflow-hidden">
        <div className="hidden grid-cols-[96px_48px_minmax(0,1fr)_64px_minmax(0,1fr)_92px_minmax(120px,170px)_64px] items-center gap-3 border-b border-line px-5 py-3 text-caption text-muted md:grid">
          <span>Fecha</span>
          <span>Liga</span>
          <span className="text-right">Local</span>
          <span className="text-center">Resultado</span>
          <span>Visitante</span>
          <span className="text-center">xG</span>
          <span>Mercado pre-partido</span>
          <span className="text-right" title="Probabilidad que el mercado daba al resultado final">P(result.)</span>
        </div>
        <div ref={listRef} className="divide-y divide-line">
          {loading &&
            Array.from({ length: 14 }).map((_, i) => (
              <div key={i} className="flex h-11 items-center gap-4 px-4">
                <Skeleton className="h-3.5 w-20" />
                <Skeleton className="h-3.5 flex-1" />
                <Skeleton className="h-2 w-36" />
              </div>
            ))}
          {rows.slice(0, limit).map((m, i) => {
            const pr = marketOnResult(m)
            const hw = m.home_goals > m.away_goals
            const aw = m.away_goals > m.home_goals
            return (
              <button
                key={m.match_id}
                data-row={i}
                onClick={() => navigate(`/partidos/${m.match_id}`)}
                onMouseEnter={() => {
                  prefetch(api.match(m.match_id))
                  setCursor(i)
                }}
                className={cx(
                  'grid w-full grid-cols-[minmax(0,1fr)_auto] items-center gap-3 px-5 py-2.5 text-left text-label transition-colors duration-[80ms] md:h-12 md:grid-cols-[96px_48px_minmax(0,1fr)_64px_minmax(0,1fr)_92px_minmax(120px,170px)_64px] md:py-0',
                  cursor === i ? 'bg-surface-2' : '',
                  'relative before:absolute before:inset-y-2 before:left-0 before:w-[2px] before:rounded-full before:bg-accent before:transition-opacity',
                  cursor === i ? 'before:opacity-100' : 'before:opacity-0',
                )}
              >
                <span className="hidden flex-col md:flex">
                  <span className="text-muted">{day(m.kickoff)}</span>
                  <span className="num text-micro text-subtle">{time(m.kickoff)}</span>
                </span>
                <span className="hidden text-micro text-subtle md:block">{LEAGUES[m.league].short}</span>
                <span className={cx('hidden items-center justify-end gap-2 truncate md:flex', hw ? 'text-fg' : 'text-muted')}>
                  <span className="truncate">{tn(m.home)}</span>
                  <TeamBadge team={m.home} size={18} />
                </span>
                <span className="num hidden justify-self-center rounded-[6px] bg-surface-3 px-2 py-0.5 font-semibold md:block">
                  {m.home_goals}–{m.away_goals}
                </span>
                <span className={cx('hidden items-center gap-2 truncate md:flex', aw ? 'text-fg' : 'text-muted')}>
                  <TeamBadge team={m.away} size={18} />
                  <span className="truncate">{tn(m.away)}</span>
                </span>
                {/* móvil: dos líneas */}
                <span className="flex min-w-0 flex-col md:hidden">
                  <span className="truncate">{tn(m.home)} <span className="num font-medium">{m.home_goals}–{m.away_goals}</span> {tn(m.away)}</span>
                  <span className="text-caption text-subtle">{day(m.kickoff)} · {LEAGUES[m.league].name}</span>
                </span>
                <span className="num text-center text-caption text-muted md:text-label">
                  {num(m.home_xg, 1)} – {num(m.away_xg, 1)}
                </span>
                <span className="hidden md:block">{m.market ? <ProbBar probs={m.market} height={5} /> : <span className="text-caption text-subtle">Sin cuotas</span>}</span>
                <span className={cx('num hidden text-right md:block', pr !== null && pr < 0.25 ? 'text-away' : 'text-muted')}>{pct(pr)}</span>
              </button>
            )
          })}
        </div>
        {rows.length > limit && (
          <button
            onClick={() => setLimit((l) => l + PAGE * 2)}
            className="w-full border-t border-line py-3 text-label text-muted transition-colors hover:bg-surface-2 hover:text-fg"
          >
            Mostrar {Math.min(PAGE * 2, rows.length - limit)} más de {rows.length - limit} restantes
          </button>
        )}
        {data && rows.length === 0 && <p className="px-4 py-10 text-center text-muted">Ningún partido coincide con «{query}».</p>}
      </Panel>
    </>
  )
}
