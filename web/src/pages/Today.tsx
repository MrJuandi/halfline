import { ArrowUpRight } from 'lucide-react'
import { motion } from 'motion/react'
import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { useCrumbs, PageHeader } from '../components/shell'
import { Badge, cx, Delta, ErrorState, Panel, PanelHeader, ProbBar, Segmented, Skeleton, Stagger, StaggerItem, TeamBadge } from '../components/ui'
import { api, prefetch, useApi, type MatchSummary, type Meta, type Upcoming, teamName as tn } from '../lib/api'
import { biggestEdge, exampleModel } from '../lib/example'
import { date, day, dayKey, LEAGUE_ORDER, LEAGUES, longDay, num, pct, relativeDays, time } from '../lib/format'

const SIDE_LABEL = { home: 'local', draw: 'empate', away: 'visitante' } as const
const chipLabel = (iso: string) => {
  const r = relativeDays(iso)
  if (r === 'Hoy' || r === 'Mañana') return r
  const d = day(iso)
  return d.charAt(0).toUpperCase() + d.slice(1)
}
const modelOf = (m: Upcoming) => m.model ?? exampleModel(`${m.home}-${m.away}-${m.kickoff}`, m.market)

/* ---------------------------------------------------------------- partido destacado */

function useNow(everyMs = 30_000) {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), everyMs)
    return () => clearInterval(id)
  }, [everyMs])
  return now
}

function countdown(iso: string, now: number) {
  const ms = Date.parse(iso) - now
  if (ms <= 0) return 'en juego'
  const h = Math.floor(ms / 3_600_000)
  const min = Math.floor((ms % 3_600_000) / 60_000)
  if (h >= 48) return `en ${Math.round(h / 24)} días`
  return h ? `en ${h} h ${min} min` : `en ${min} min`
}

function NextMatch({ m }: { m: Upcoming }) {
  const now = useNow()
  const model = modelOf(m)
  const parts = [
    { k: 'home' as const, label: tn(m.home), color: 'text-home' },
    { k: 'draw' as const, label: 'Empate', color: 'text-draw' },
    { k: 'away' as const, label: tn(m.away), color: 'text-away' },
  ]
  return (
    <Panel className="relative overflow-hidden p-5 md:p-7">
      <div className="flex flex-wrap items-center justify-between gap-3 text-label text-muted">
        <span>
          Siguiente partido · {LEAGUES[m.league].name} · {relativeDays(m.kickoff)}, {time(m.kickoff)}
        </span>
        <span className="num rounded-full bg-accent-soft px-2.5 py-1 font-medium text-accent">{countdown(m.kickoff, now)}</span>
      </div>
      <div className="mt-6 grid grid-cols-[1fr_auto_1fr] items-center gap-4">
        <div className="flex min-w-0 flex-col items-start gap-3 md:flex-row md:items-center">
          <TeamBadge team={m.home} size={56} />
          <span className="truncate text-[22px] leading-7 font-semibold tracking-[-0.02em] md:text-[28px] md:leading-8">{tn(m.home)}</span>
        </div>
        <span className="text-[15px] text-subtle">vs</span>
        <div className="flex min-w-0 flex-col items-end gap-3 md:flex-row-reverse md:items-center">
          <TeamBadge team={m.away} size={56} />
          <span className="truncate text-right text-[22px] leading-7 font-semibold tracking-[-0.02em] md:text-[28px] md:leading-8">{tn(m.away)}</span>
        </div>
      </div>
      <div className="mt-7">
        <ProbBar probs={model} height={12} />
        <div className="mt-3 grid grid-cols-3 gap-3">
          {parts.map((p, i) => (
            <div key={p.k} className={cx(i === 1 && 'text-center', i === 2 && 'text-right')}>
              <div className={cx('num text-[32px] leading-9 font-semibold tracking-[-0.03em]', p.color)}>{pct(model[p.k])}</div>
              <div className="truncate text-label text-muted">{p.label}</div>
            </div>
          ))}
        </div>
      </div>
      <div className="mt-5 flex items-center gap-2 text-caption text-muted">
        {!m.model && <Badge tone="warn">Modelo de ejemplo</Badge>}
        {m.market ? <span>Mercado: {pct(m.market.home)} · {pct(m.market.draw)} · {pct(m.market.away)}</span> : <span>Las cuotas de la jornada aún no se han publicado.</span>}
      </div>
    </Panel>
  )
}

/** Partidos por liga en los próximos días: cuánto fútbol queda por delante. */
function Ahead({ data }: { data: Upcoming[] }) {
  const counts = LEAGUE_ORDER.map((c) => ({ c, n: data.filter((m) => m.league === c).length }))
  const max = Math.max(1, ...counts.map((x) => x.n))
  return (
    <Panel className="flex flex-col p-5 md:p-7">
      <div className="text-label text-muted">Próximas dos semanas</div>
      <div className="num mt-1 text-[48px] leading-[52px] font-semibold tracking-[-0.04em]">{data.length}</div>
      <div className="text-label text-muted">partidos en cinco ligas</div>
      <ul className="mt-auto space-y-2.5 pt-6">
        {counts.map(({ c, n }, i) => (
          <li key={c} className="grid grid-cols-[104px_1fr_28px] items-center gap-3 text-label">
            <span className="truncate text-muted">{LEAGUES[c].name}</span>
            <span className="h-2 overflow-hidden rounded-full bg-surface-3">
              <motion.span
                className="block h-full rounded-full bg-fg"
                initial={{ width: 0 }}
                animate={{ width: `${(n / max) * 100}%` }}
                transition={{ duration: 0.7, delay: 0.2 + i * 0.06, ease: [0.16, 1, 0.3, 1] }}
              />
            </span>
            <span className="num text-right">{n}</span>
          </li>
        ))}
      </ul>
    </Panel>
  )
}

/* ---------------------------------------------------------------- calendario */

function UpcomingRow({ m, showMarket }: { m: Upcoming; showMarket: boolean }) {
  const model = modelOf(m)
  const edge = m.market ? biggestEdge(model, m.market) : null
  return (
    <div
      className={cx(
        'grid grid-cols-[52px_minmax(0,1fr)] items-center gap-x-4 gap-y-3 px-5 py-3 transition-colors hover:bg-surface-2/60',
        showMarket
          ? 'md:grid-cols-[56px_minmax(0,1fr)_minmax(150px,200px)_minmax(150px,200px)_80px]'
          : 'md:grid-cols-[56px_minmax(0,1fr)_minmax(220px,300px)]',
      )}
    >
      <span className="flex flex-col">
        <span className="num text-[15px] font-semibold">{time(m.kickoff)}</span>
        <span className="text-caption text-muted">{LEAGUES[m.league].short}</span>
      </span>
      <div className="flex min-w-0 flex-col gap-1.5">
        {[m.home, m.away].map((t) => (
          <span key={t} className="flex items-center gap-2.5 truncate text-[14px]">
            <TeamBadge team={t} size={20} />
            <span className="truncate">{tn(t)}</span>
          </span>
        ))}
      </div>
      <div className="col-span-2 flex flex-col gap-1.5 md:col-span-1">
        <div className="flex items-baseline justify-between text-caption text-muted">
          <span>Modelo{!m.model && <span className="text-away"> · ejemplo</span>}</span>
          <span className="num">{pct(model.home)} · {pct(model.draw)} · {pct(model.away)}</span>
        </div>
        <ProbBar probs={model} />
      </div>
      {showMarket && (
        <div className="hidden flex-col gap-1.5 md:flex">
          <div className="flex items-baseline justify-between text-caption text-muted">
            <span>Mercado</span>
            {m.market && <span className="num">{pct(m.market.home)} · {pct(m.market.draw)} · {pct(m.market.away)}</span>}
          </div>
          {m.market ? <ProbBar probs={m.market} muted /> : <span className="text-caption text-subtle">Sin cuotas todavía</span>}
        </div>
      )}
      {showMarket && (
        <div className="hidden text-right md:block">
          {edge ? (
            <div className="flex flex-col items-end">
              <Delta value={edge.delta} />
              <span className="text-micro text-subtle">{SIDE_LABEL[edge.side]}</span>
            </div>
          ) : (
            <span className="text-caption text-subtle">–</span>
          )}
        </div>
      )}
    </div>
  )
}

function Calendar({ data }: { data: Upcoming[] }) {
  const [params, setParams] = useSearchParams()
  const league = params.get('liga') ?? 'all'
  const filtered = league === 'all' ? data : data.filter((m) => m.league === league)
  const days = useMemo(() => {
    const g = new Map<string, Upcoming[]>()
    filtered.forEach((m) => g.set(dayKey(m.kickoff), [...(g.get(dayKey(m.kickoff)) ?? []), m]))
    return [...g.entries()]
  }, [filtered])
  const picked = params.get('dia')
  const active = days.find(([k]) => k === picked) ?? days[0]
  const showMarket = data.some((m) => m.market)
  const set = (k: string, v: string | null) => {
    const p = new URLSearchParams(params)
    if (v) p.set(k, v)
    else p.delete(k)
    setParams(p, { replace: true })
  }

  return (
    <Panel className="overflow-hidden">
      <div className="flex flex-wrap items-center justify-between gap-3 px-5 pt-4">
        <h2 className="text-[16px] font-semibold tracking-[-0.01em]">Calendario</h2>
        <Segmented
          id="today-league"
          value={league}
          onChange={(v) => set('liga', v === 'all' ? null : v)}
          options={[{ value: 'all', label: 'Todas' }, ...LEAGUE_ORDER.map((c) => ({ value: c, label: LEAGUES[c].short }))]}
        />
      </div>
      {/* Tira de días: cada uno con su número de partidos */}
      <div className="mt-4 flex flex-wrap gap-1.5 px-5 pb-3" role="tablist" aria-label="Día">
        {days.map(([k, ms]) => {
          const on = active?.[0] === k
          return (
            <button
              key={k}
              role="tab"
              aria-selected={on}
              onClick={() => set('dia', k)}
              className={cx('relative flex shrink-0 flex-col items-start rounded-[10px] px-3.5 py-2 text-left transition-[color,transform] active:scale-[0.97]', on ? 'text-fg' : 'text-muted hover:bg-surface-2 hover:text-fg')}
            >
              {on && <motion.span layoutId="today-day" className="absolute inset-0 rounded-[10px] bg-surface-3" transition={{ type: 'spring', bounce: 0.1, duration: 0.35 }} />}
              <span className="relative text-label font-medium">{chipLabel(ms[0].kickoff)}</span>
              <span className="num relative text-caption text-muted">{ms.length} partidos</span>
            </button>
          )
        })}
      </div>
      {active ? (
        <motion.div key={`${active[0]}-${league}`} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }} className="divide-y divide-line border-t border-line">
          {active[1].map((m) => (
            <UpcomingRow key={m.espn_id} m={m} showMarket={showMarket} />
          ))}
        </motion.div>
      ) : (
        <p className="px-5 py-10 text-center text-muted">No hay partidos programados para esta liga en las próximas dos semanas.</p>
      )}
    </Panel>
  )
}

/* ---------------------------------------------------------------- columna derecha */

/** Partidos recientes donde el xG contó otra historia que el marcador. */
function Surprises({ matches }: { matches: MatchSummary[] }) {
  const navigate = useNavigate()
  const rows = matches
    .filter((m) => m.home_xg !== null && m.away_xg !== null)
    .map((m) => {
      const gd = m.home_goals - m.away_goals
      const xd = (m.home_xg as number) - (m.away_xg as number)
      return { m, gap: Math.sign(gd) !== Math.sign(Math.round(xd * 2) / 2) ? Math.abs(xd) : 0 }
    })
    .filter((r) => r.gap > 0.6)
    .sort((a, b) => b.gap - a.gap)
    .slice(0, 5)
  return (
    <Panel>
      <PanelHeader title="El marcador no lo cuenta todo" sub="Últimos 7 días · resultado contrario al xG" />
      {rows.length === 0 && <p className="px-5 pb-5 text-muted">Ningún resultado contradijo el xG con claridad.</p>}
      <ul className="px-2 pb-2">
        {rows.map(({ m }) => {
          const total = (m.home_xg as number) + (m.away_xg as number) || 1
          return (
            <li key={m.match_id}>
              <button
                onClick={() => navigate(`/partidos/${m.match_id}`)}
                onMouseEnter={() => prefetch(api.match(m.match_id))}
                className="group w-full rounded-[10px] px-3 py-2.5 text-left transition-colors hover:bg-surface-2"
              >
                <span className="flex items-center justify-between gap-2 text-label">
                  <span className="truncate">
                    {tn(m.home)} <span className="num font-semibold">{m.home_goals}–{m.away_goals}</span> {tn(m.away)}
                  </span>
                  <ArrowUpRight size={14} className="shrink-0 text-subtle opacity-0 transition-opacity group-hover:opacity-100" />
                </span>
                <span className="mt-2 flex h-1.5 gap-[2px] overflow-hidden rounded-full">
                  <span className="bg-home" style={{ flexGrow: m.home_xg as number }} />
                  <span className="bg-away" style={{ flexGrow: m.away_xg as number }} />
                </span>
                <span className="num mt-1.5 flex justify-between text-caption text-muted">
                  <span>xG {num(m.home_xg)}</span>
                  <span>{LEAGUES[m.league].name}</span>
                  <span>{num(m.away_xg)}</span>
                </span>
                <span className="sr-only">{pct((m.home_xg as number) / total)} del xG para el local</span>
              </button>
            </li>
          )
        })}
      </ul>
    </Panel>
  )
}

function RecentResults({ matches }: { matches: MatchSummary[] }) {
  return (
    <Panel>
      <PanelHeader
        title="Resultados recientes"
        aside={
          <Link to="/partidos" className="text-label text-muted transition-colors hover:text-fg">
            Ver todos
          </Link>
        }
      />
      <ul className="px-2 pb-2">
        {matches.slice(0, 8).map((m) => {
          const hw = m.home_goals > m.away_goals
          const aw = m.away_goals > m.home_goals
          return (
            <li key={m.match_id}>
              <Link
                to={`/partidos/${m.match_id}`}
                onMouseEnter={() => prefetch(api.match(m.match_id))}
                className="grid grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] items-center gap-3 rounded-[10px] px-3 py-2 text-label transition-colors hover:bg-surface-2"
              >
                <span className={cx('flex min-w-0 items-center justify-end gap-2', hw ? 'font-medium text-fg' : 'text-muted')}>
                  <span className="truncate">{tn(m.home)}</span>
                  <TeamBadge team={m.home} size={16} />
                </span>
                <span className="num rounded-[6px] bg-surface-3 px-2 py-0.5 text-center font-semibold">
                  {m.home_goals}–{m.away_goals}
                </span>
                <span className={cx('flex min-w-0 items-center gap-2', aw ? 'font-medium text-fg' : 'text-muted')}>
                  <TeamBadge team={m.away} size={16} />
                  <span className="truncate">{tn(m.away)}</span>
                </span>
              </Link>
            </li>
          )
        })}
      </ul>
    </Panel>
  )
}

/* ---------------------------------------------------------------- página */

export default function Today() {
  const { data: meta } = useApi<Meta>(api.meta)
  const season = meta?.leagues[0]?.seasons.at(-1)
  const { data: recent } = useApi<MatchSummary[]>(season ? api.matches({ season, limit: 60 }) : null)
  const { data: upcoming, error } = useApi<Upcoming[]>(api.upcoming(14))
  useCrumbs([{ label: 'Hoy' }])

  const lastWeek = useMemo(() => {
    if (!recent?.length) return []
    const end = Date.parse(recent[0].kickoff ?? '')
    return recent.filter((m) => m.kickoff && end - Date.parse(m.kickoff) < 7 * 86_400_000)
  }, [recent])

  return (
    <>
      <PageHeader
        title={longDay(new Date().toISOString())}
        sub={meta ? <>{meta.counts.matches.toLocaleString('es-ES')} partidos analizados en 5 ligas · datos hasta el {date(meta.data_through)}</> : <Skeleton className="h-4 w-72" />}
      />
      {error && <ErrorState message="No se pudo cargar el calendario." />}
      <Stagger className="flex flex-col gap-6">
        <StaggerItem className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_340px]">
          {upcoming?.[0] ? <NextMatch m={upcoming[0]} /> : <Skeleton className="h-[300px] w-full rounded-panel" />}
          {upcoming ? <Ahead data={upcoming} /> : <Skeleton className="h-[300px] w-full rounded-panel" />}
        </StaggerItem>
        <StaggerItem className="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1fr)_340px]">
          {upcoming ? <Calendar data={upcoming} /> : <Skeleton className="h-[480px] w-full rounded-panel" />}
          <div className="flex flex-col gap-6">
            {recent ? <RecentResults matches={recent} /> : <Skeleton className="h-80 w-full rounded-panel" />}
            {recent ? <Surprises matches={lastWeek} /> : <Skeleton className="h-64 w-full rounded-panel" />}
          </div>
        </StaggerItem>
      </Stagger>
    </>
  )
}
