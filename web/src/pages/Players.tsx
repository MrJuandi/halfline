import { extent } from 'd3-array'
import { scaleLinear, scaleSqrt } from 'd3-scale'
import { AnimatePresence, motion } from 'motion/react'
import { Search } from 'lucide-react'
import { useLayoutEffect, useMemo, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { PageHeader, useCrumbs } from '../components/shell'
import { PlayerPhoto } from '../components/team'
import { cx, ErrorState, Panel, PanelHeader, Segmented, Skeleton, TeamBadge } from '../components/ui'
import { playerUrl, playersUrl, useApi, type PlayerDot, type PlayerMap, type PlayerProfile, type PlayerRole, teamName as tn } from '../lib/api'
import { declutter, LEAGUE_ORDER, LEAGUES, num, seasonLabel } from '../lib/format'

const ease = [0.16, 1, 0.3, 1] as const

function useWidth<T extends HTMLElement>(): [React.RefObject<T | null>, number] {
  const ref = useRef<T>(null)
  const [w, setW] = useState(0)
  useLayoutEffect(() => {
    if (!ref.current) return
    const ro = new ResizeObserver(([e]) => setW(Math.round(e.contentRect.width)))
    ro.observe(ref.current)
    return () => ro.disconnect()
  }, [])
  return [ref, w]
}

/* ---------------------------------------------------------------- mapa de roles */

function RoleMap({ data, selected, onSelect, query, role }: { data: PlayerMap; selected: string | null; onSelect: (id: string) => void; query: string; role: string }) {
  const [ref, width] = useWidth<HTMLDivElement>()
  const [hover, setHover] = useState<PlayerDot | null>(null)
  const H = 600
  const m = 24
  const [x0, x1] = extent(data.players, (p) => p.pc1) as [number, number]
  const [y0, y1] = extent(data.players, (p) => p.pc2) as [number, number]
  const x = scaleLinear().domain([x0 - 0.3, x1 + 0.3]).range([m, Math.max(m + 1, width - m)])
  const y = scaleLinear().domain([y0 - 0.3, y1 + 0.3]).range([H - m - 16, m])
  const r = scaleSqrt().domain(data.season === 'now' ? [450, 1000] : [900, 3400]).range([2.2, 5]).clamp(true)
  const roleColor = useMemo(() => Object.fromEntries(data.roles.roles.map((ro) => [ro.key, ro.color])), [data])
  const q = query.trim().toLowerCase().normalize('NFD').replace(/\p{Diacritic}/gu, '')
  const match = (p: PlayerDot) => !q || `${p.name} ${tn(p.team)}`.toLowerCase().normalize('NFD').replace(/\p{Diacritic}/gu, '').includes(q)
  const sel = data.players.find((p) => p.player_id === selected)
  return (
    <div ref={ref} className="relative w-full" style={{ height: H }}>
      {width > 0 && (
        <svg width={width} height={H} className="block">
          <defs>
            <pattern id="pdots" width={22} height={22} patternUnits="userSpaceOnUse">
              <circle cx={1} cy={1} r={0.8} fill="var(--border-strong)" />
            </pattern>
            <filter id="pglow" x="-50%" y="-50%" width="200%" height="200%">
              <feGaussianBlur stdDeviation={width / 45} />
            </filter>
          </defs>
          <rect width={width} height={H} fill="url(#pdots)" opacity={0.6} />
          <g filter="url(#pglow)" opacity={0.45}>
            {data.roles.roles.map((ro) => (
              <circle key={ro.key} cx={x(ro.pc[0])} cy={y(ro.pc[1])} r={width / 12} fill={ro.color} opacity={0.35} />
            ))}
          </g>
          <text x={width - m} y={H - 8} textAnchor="end" fontSize={12} fill="var(--text-muted)">más cerca del gol →</text>
          <text x={m} y={16} fontSize={12} fill="var(--text-muted)">↑ más creación</text>
          {data.players.map((p) => {
            const on = (role === 'all' || p.role === role) && match(p)
            return (
              <circle
                key={p.player_id + p.team}
                cx={x(p.pc1)}
                cy={y(p.pc2)}
                r={r(p.minutes)}
                fill={roleColor[p.role]}
                opacity={on ? (q ? 1 : 0.75) : 0.08}
                onMouseEnter={() => setHover(p)}
                onMouseLeave={() => setHover(null)}
                onClick={() => onSelect(p.player_id)}
                className="cursor-pointer"
              />
            )
          })}
          {declutter(data.roles.roles.map((ro) => ({ ro, x: x(ro.pc[0]), y: y(ro.pc[1]), text: ro.name }))).map(({ ro, x: lx, ly }) => (
            <text key={ro.key} x={lx} y={ly} textAnchor="middle" fontSize={11} fontWeight={700} letterSpacing="0.04em" fill={ro.color} stroke="var(--bg)" strokeWidth={4} strokeLinejoin="round" style={{ paintOrder: 'stroke' }} pointerEvents="none">
              {ro.name.toUpperCase()}
            </text>
          ))}
          {sel && (
            <g pointerEvents="none">
              <motion.circle cx={x(sel.pc1)} cy={y(sel.pc2)} initial={{ r: 30, opacity: 0 }} animate={{ r: 10, opacity: 1 }} transition={{ duration: 0.5, ease }} fill="none" stroke="var(--text)" strokeWidth={2} />
              <text x={x(sel.pc1) + 14} y={y(sel.pc2) + 4} fontSize={12} fontWeight={600} fill="var(--text)" stroke="var(--bg)" strokeWidth={4} style={{ paintOrder: 'stroke' }}>{sel.name}</text>
            </g>
          )}
        </svg>
      )}
      {hover && (
        <div className="pointer-events-none absolute z-10 flex items-center gap-2.5 rounded-panel border border-line-strong bg-surface-2 px-3 py-2 float-shadow" style={{ left: Math.min(x(hover.pc1) + 14, width - 240), top: Math.max(y(hover.pc2) - 54, 4) }}>
          <PlayerPhoto name={hover.name} photo={hover.photo} size={30} />
          <div>
            <div className="text-label font-medium">{hover.name}</div>
            <div className="text-caption text-subtle">{tn(hover.team)} · {num(hover.minutes, 0)} min · {hover.goals} G {hover.assists} A</div>
          </div>
        </div>
      )}
    </div>
  )
}

/* ---------------------------------------------------------------- perfil */

function Profile({ id, roles, onSelect }: { id: string; roles: Record<string, PlayerRole>; onSelect: (id: string) => void }) {
  const [which, setWhich] = useState<number | 'now' | undefined>(undefined)
  const { data: p, error } = useApi<PlayerProfile>(playerUrl(id, which))
  if (error) return <ErrorState message="Este jugador no tiene perfil." hint="Hacen falta al menos 900 minutos en una temporada." />
  if (!p) return <Skeleton className="h-[640px] w-full" />
  const role = roles[p.role]
  const feats = [...p.features].sort((a, b) => b.pct_role - a.pct_role)
  return (
    <motion.div key={id} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3, ease }} className="flex flex-col gap-6">
      <Panel className="relative overflow-hidden">
        <div className="absolute inset-x-0 top-0 h-1" style={{ background: role.color }} />
        <div className="relative flex items-center gap-4 px-5 py-5">
          <PlayerPhoto name={p.name} photo={p.photo} size={64} />
          <div className="min-w-0">
            <div className="text-[22px] font-semibold leading-7 tracking-[-0.02em]">{p.name}</div>
            <Link to={`/equipos/${p.league}/${encodeURIComponent(p.team)}?temporada=${p.season}&tab=plantilla`} className="mt-1 flex items-center gap-1.5 text-label text-muted hover:text-fg">
              <TeamBadge team={p.team} size={16} /> {tn(p.team)} · {p.window === 'now' ? 'estado actual' : seasonLabel(p.season)}
            </Link>
            <div className="mt-2 inline-flex h-6 items-center rounded-full px-2.5 text-caption font-medium" style={{ background: `color-mix(in srgb, ${role.color} 16%, transparent)`, color: role.color }}>
              {role.name}
            </div>
            {p.window === 'now' && (
              <div className="mt-1.5 text-micro text-subtle">
                Últimos {num(p.minutes, 0)} minutos · {p.this_season} partidos de 26/27{p.short_sample ? ' · muestra corta' : ''}
              </div>
            )}
          </div>
        </div>
        {(p.seasons.length > 0 || p.has_now) && (
          <div className="relative flex flex-wrap gap-1 border-t border-line px-4 py-2.5">
            {[...p.seasons.map((x) => ({ v: x as number | 'now', l: seasonLabel(x) })), ...(p.has_now ? [{ v: 'now' as const, l: 'Ahora' }] : [])].map((o) => {
              const active = (p.window === 'now' && o.v === 'now') || (p.window === 'season' && o.v === p.season)
              return (
                <button
                  key={String(o.v)}
                  onClick={() => setWhich(o.v)}
                  className={cx('h-6 rounded-full px-2 text-micro transition-colors', active ? 'bg-surface-3 text-fg' : 'text-subtle hover:text-fg')}
                >
                  {o.l}
                </button>
              )
            })}
          </div>
        )}
        <div className="relative grid grid-cols-4 divide-x divide-line border-t border-line">
          {[
            ['Minutos', num(p.minutes, 0)],
            ['Goles · xG', `${p.goals} · ${num(p.xg, 1)}`],
            ['Asist. · xA', `${p.assists} · ${num(p.xa, 1)}`],
            ['Nota', num(p.rating, 2)],
          ].map(([k, v]) => (
            <div key={k} className="px-4 py-3">
              <div className="text-micro text-subtle">{k}</div>
              <div className="num mt-0.5 text-label font-medium">{v}</div>
            </div>
          ))}
        </div>
      </Panel>

      <Panel>
        <PanelHeader title="Huella" sub={`Percentil dentro de su rol (${role.name.toLowerCase()}) · valores por 90 minutos`} />
        <ul className="space-y-1.5 p-4">
          {feats.map((f, i) => (
            <li key={f.key} className="grid grid-cols-[150px_minmax(0,1fr)_56px] items-center gap-3 text-caption">
              <span className="truncate text-muted">{f.label}</span>
              <span className="relative h-2 rounded-full bg-surface-3">
                <motion.span
                  className="absolute inset-y-0 left-0 rounded-full"
                  style={{ background: role.color, opacity: 0.35 + (f.pct_role / 100) * 0.65 }}
                  initial={{ width: 0 }}
                  animate={{ width: `${f.pct_role}%` }}
                  transition={{ duration: 0.55, delay: i * 0.02, ease }}
                />
              </span>
              <span className="num text-right text-muted">{num(f.value, f.value >= 10 ? 0 : 2)}</span>
            </li>
          ))}
        </ul>
      </Panel>

      <Panel>
        <PanelHeader title="Se parece a" sub="Jugadores-temporada con el perfil más cercano en las cinco ligas" />
        <ul className="divide-y divide-line">
          {p.similar.map((s) => (
            <li key={s.player_id + s.season}>
              <button onClick={() => onSelect(s.player_id)} className="grid w-full grid-cols-[32px_minmax(0,1fr)_96px] items-center gap-3 px-4 py-2 text-left transition-colors hover:bg-surface-2">
                <PlayerPhoto name={s.name} photo={s.photo} size={30} />
                <span className="min-w-0">
                  <span className="block truncate text-label font-medium">{s.name}</span>
                  <span className="block truncate text-caption text-subtle">
                    {tn(s.team)} · {seasonLabel(s.season)} · <span style={{ color: roles[s.role]?.color }}>{roles[s.role]?.name}</span>
                  </span>
                </span>
                <span className="flex items-center gap-2">
                  <span className="h-1.5 flex-1 overflow-hidden rounded-full bg-surface-3">
                    <span className="block h-full rounded-full bg-accent" style={{ width: `${s.similarity * 100}%` }} />
                  </span>
                  <span className="num w-7 text-right text-caption text-muted">{Math.round(s.similarity * 100)}</span>
                </span>
              </button>
            </li>
          ))}
        </ul>
      </Panel>

      {p.history.length > 1 && (
        <Panel>
          <PanelHeader title="Trayectoria" sub="Rol en cada temporada con más de 900 minutos" />
          <ol className="flex flex-wrap gap-2 p-4">
            {p.history.map((h) => (
              <li key={h.season + h.team} className="rounded-ctl bg-surface-2 px-2.5 py-1.5 text-caption">
                <span className="num text-subtle">{seasonLabel(h.season)}</span>{' '}
                <span className="text-muted">{tn(h.team)}</span>{' '}
                <span style={{ color: roles[h.role]?.color }}>{roles[h.role]?.name}</span>
              </li>
            ))}
          </ol>
        </Panel>
      )}
    </motion.div>
  )
}

/* ---------------------------------------------------------------- página */

export default function Players() {
  const [params, setParams] = useSearchParams()
  const rawSeason = params.get('temporada')
  const season: number | 'now' = !rawSeason || rawSeason === 'now' ? 'now' : Number(rawSeason)
  const league = params.get('liga') ?? 'all'
  const selected = params.get('jugador')
  const [query, setQuery] = useState('')
  const [role, setRole] = useState('all')
  const { data, error } = useApi<PlayerMap>(playersUrl(season, league))
  useCrumbs([{ label: 'Jugadores' }])
  const set = (k: string, v: string | null) => {
    const p = new URLSearchParams(params)
    if (v === null) p.delete(k)
    else p.set(k, v)
    setParams(p, { replace: true })
  }
  const roles = useMemo(() => Object.fromEntries((data?.roles.roles ?? []).map((r) => [r.key, r])), [data])
  const results = useMemo(() => {
    const q = query.trim().toLowerCase().normalize('NFD').replace(/\p{Diacritic}/gu, '')
    if (!data || q.length < 2) return []
    return data.players.filter((p) => p.name.toLowerCase().normalize('NFD').replace(/\p{Diacritic}/gu, '').includes(q)).slice(0, 6)
  }, [data, query])

  if (error) return <ErrorState message="No se pudieron cargar los jugadores." hint="Genera los perfiles con python -m futdata.player_styles y reinicia la API." />

  return (
    <>
      <PageHeader
        title="Jugadores"
        sub={
          data
            ? data.season === 'now'
              ? `${data.players.length.toLocaleString('es-ES')} jugadores según sus últimos 900 minutos (mínimo 450), agrupados en nueve roles según lo que hacen por 90 minutos`
              : `${data.players.length.toLocaleString('es-ES')} jugadores con más de 900 minutos en ${seasonLabel(data.season)}, agrupados en nueve roles según lo que hacen por 90 minutos`
            : ' '
        }
      />
      {!data ? (
        <Skeleton className="h-[640px] w-full" />
      ) : (
        <div className="grid grid-cols-1 gap-6 2xl:grid-cols-[minmax(0,1fr)_440px]">
          <div className="flex min-w-0 flex-col gap-4">
            <div className="flex flex-wrap items-center gap-2">
              <Segmented
                id="pl-season"
                value={data.season}
                onChange={(v) => set('temporada', v === 'now' ? null : String(v))}
                options={[...data.seasons.map((x) => ({ value: x as number | 'now', label: seasonLabel(x) })), { value: 'now' as const, label: 'Ahora' }]}
              />
              <Segmented
                id="pl-league"
                value={league}
                onChange={(v) => set('liga', v === 'all' ? null : v)}
                options={[{ value: 'all', label: 'Todas' }, ...LEAGUE_ORDER.map((c) => ({ value: c, label: LEAGUES[c].short }))]}
              />
              <div className="relative">
                <label className="flex h-9 w-64 items-center gap-2 rounded-ctl bg-surface-1 px-3 text-label transition-colors focus-within:bg-surface-3">
                  <Search size={14} className="text-subtle" />
                  <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Buscar jugador" className="w-full bg-transparent outline-none placeholder:text-subtle" />
                </label>
                <AnimatePresence>
                  {results.length > 0 && (
                    <motion.ul initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} className="absolute z-20 mt-1 w-80 overflow-hidden rounded-panel border border-line-strong bg-surface-2 p-1 float-shadow">
                      {results.map((p) => (
                        <li key={p.player_id}>
                          <button
                            onClick={() => {
                              set('jugador', p.player_id)
                              setQuery('')
                            }}
                            className="flex w-full items-center gap-2.5 rounded-ctl px-2 py-1.5 text-left hover:bg-surface-3"
                          >
                            <PlayerPhoto name={p.name} photo={p.photo} size={24} />
                            <span className="min-w-0 flex-1 truncate text-label">{p.name}</span>
                            <span className="truncate text-caption text-subtle">{tn(p.team)}</span>
                          </button>
                        </li>
                      ))}
                    </motion.ul>
                  )}
                </AnimatePresence>
              </div>
            </div>
            <Panel className="overflow-hidden">
              <RoleMap data={data} selected={selected} onSelect={(id) => set('jugador', id)} query={query} role={role} />
            </Panel>
            <div className="flex flex-wrap gap-1.5">
              <button onClick={() => setRole('all')} className={cx('h-8 rounded-full px-3 text-caption font-medium transition-[background-color,transform] active:scale-95', role === 'all' ? 'bg-surface-3 text-fg' : 'bg-surface-1 text-muted hover:text-fg')}>
                Todos los roles
              </button>
              {data.roles.roles.map((r) => (
                <button
                  key={r.key}
                  onClick={() => setRole(role === r.key ? 'all' : r.key)}
                  title={r.description}
                  className={cx('flex h-8 items-center gap-1.5 rounded-full px-3 text-caption font-medium transition-[background-color,transform] active:scale-95', role === r.key ? 'bg-surface-3 text-fg' : 'bg-surface-1 text-muted hover:text-fg')}
                >
                  <span className="size-2 rounded-full" style={{ background: r.color }} />
                  {r.name}
                </button>
              ))}
            </div>
          </div>
          <div>
            {selected ? (
              <Profile key={selected} id={selected} roles={roles} onSelect={(id) => set('jugador', id)} />
            ) : (
              <Panel className="p-6">
                <h3 className="text-h3 font-semibold">Elige un jugador</h3>
                <p className="mt-2 text-label text-muted">
                  Pulsa un punto del mapa o búscalo por su nombre. Verás su huella frente a los de su rol y los jugadores de las cinco ligas con el perfil más parecido.
                </p>
                <div className="mt-5 space-y-3">
                  {data.roles.roles.map((r) => (
                    <div key={r.key} className="flex gap-3">
                      <span className="mt-1.5 size-2 shrink-0 rounded-full" style={{ background: r.color }} />
                      <div>
                        <div className="text-label font-medium">{r.name}</div>
                        <div className="text-caption text-subtle">{r.description}</div>
                      </div>
                    </div>
                  ))}
                </div>
              </Panel>
            )}
          </div>
        </div>
      )}
    </>
  )
}
