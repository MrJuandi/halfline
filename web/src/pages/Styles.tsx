import { scaleLinear } from 'd3-scale'
import { motion } from 'motion/react'
import { useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { PageHeader, useCrumbs } from '../components/shell'
import { archetypeOf, Fingerprint, MiniMove, StyleMap } from '../components/stylemap'
import { ErrorState, Panel, PanelHeader, Segmented, Skeleton, TeamBadge } from '../components/ui'
import { api, useApi, type ArchetypeKey, type Styles as StylesData, teamName as tn } from '../lib/api'
import { LEAGUE_ORDER, LEAGUES, num, pct, seasonLabel } from '../lib/format'

const ease = [0.16, 1, 0.3, 1] as const

function Chapter({ title, lead, children }: { title: string; lead: React.ReactNode; children: React.ReactNode }) {
  return (
    <section className="mt-24 first:mt-0">
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, margin: '-60px' }}
        transition={{ duration: 0.5, ease }}
        className="mb-8"
      >
        <div>
          <h2 className="text-[30px] font-semibold leading-9 tracking-[-0.03em]">{title}</h2>
          <div className="mt-3 max-w-[720px] text-[16px] leading-[1.6] text-muted">{lead}</div>
        </div>
      </motion.div>
      {children}
    </section>
  )
}

function LeagueAccents({ s }: { s: StylesData }) {
  const W = 900
  const H = 280
  const xs = s.leagues.map((l) => l.pc1)
  const ys = s.leagues.map((l) => l.pc2)
  const padX = (Math.max(...xs) - Math.min(...xs)) * 0.35 + 0.1
  const padY = (Math.max(...ys) - Math.min(...ys)) * 0.45 + 0.1
  const x = scaleLinear().domain([Math.min(...xs, 0) - padX, Math.max(...xs, 0) + padX]).range([40, W - 160])
  const y = scaleLinear().domain([Math.min(...ys, 0) - padY, Math.max(...ys, 0) + padY]).range([H - 30, 30])
  // Etiquetas sin solaparse: se ordenan por altura y se separan al menos 18px
  const labels = [...s.leagues].sort((a, b) => y(a.pc2) - y(b.pc2)).reduce<{ l: (typeof s.leagues)[number]; ly: number }[]>((acc, l) => {
    const prev = acc.at(-1)
    const ly = prev ? Math.max(y(l.pc2), prev.ly + 18) : y(l.pc2)
    return [...acc, { l, ly }]
  }, [])
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="block w-full">
      <line x1={x(0)} x2={x(0)} y1={10} y2={H - 10} stroke="var(--border-strong)" strokeDasharray="2 5" />
      <line x1={20} x2={W - 20} y1={y(0)} y2={y(0)} stroke="var(--border-strong)" strokeDasharray="2 5" />
      <text x={W - 20} y={y(0) - 8} textAnchor="end" fontSize={11} fill="var(--text-subtle)">más dominio →</text>
      <text x={x(0) + 8} y={20} fontSize={11} fill="var(--text-subtle)">↑ más físico y por fuera</text>
      {labels.map(({ l, ly }, i) => (
        <motion.g
          key={l.league}
          initial={{ opacity: 0 }}
          whileInView={{ opacity: 1 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5, delay: i * 0.08, ease }}
        >
          <line x1={x(l.pc1)} y1={y(l.pc2)} x2={x(l.pc1) + 22} y2={ly} stroke="var(--border-strong)" />
          <circle cx={x(l.pc1)} cy={y(l.pc2)} r={6} fill="var(--accent)" stroke="var(--surface-1)" strokeWidth={2} />
          <text x={x(l.pc1) + 26} y={ly + 4} fontSize={13} fontWeight={600} fill="var(--text)">{LEAGUES[l.league].name}</text>
          <text x={x(l.pc1) + 26 + LEAGUES[l.league].name.length * 7.6 + 6} y={ly + 4} fontSize={11} fill="var(--text-subtle)" className="num">
            {num(l.pc1, 2)} · {num(l.pc2, 2)}
          </text>
        </motion.g>
      ))}
    </svg>
  )
}

/** La clusterización en formato lista: cada arquetipo con sus equipos (temporada y liga elegidas). */
function ArchetypeColumns({ s, season, league, onPick, onHover }: { s: StylesData; season: number | 'now'; league: string; onPick: (k: string) => void; onHover: (k: ArchetypeKey | null) => void }) {
  const pool = (season === 'now' ? s.current : s.teams.filter((t) => t.season === season)).filter((t) => league === 'all' || t.league === league)
  const groups = s.archetypes
    .slice()
    .sort((a, b) => b.pc[0] - a.pc[0])
    .map((a) => ({ a, teams: pool.filter((t) => t.archetype === a.key).sort((x, y) => y.pc1 - x.pc1) }))
  return (
    <div className="mt-4 grid grid-cols-2 gap-2 md:grid-cols-3 xl:grid-cols-6">
      {groups.map(({ a, teams }) => (
        <div key={a.key} className="rounded-panel bg-surface-1 p-3" onMouseEnter={() => onHover(a.key)} onMouseLeave={() => onHover(null)}>
          <div className="flex items-baseline justify-between gap-2">
            <span className="truncate text-label font-semibold" style={{ color: a.color }}>{a.name}</span>
            <span className="num text-caption text-subtle">{teams.length}</span>
          </div>
          <p className="mt-1 line-clamp-2 text-micro leading-4 text-subtle">{a.description}</p>
          <ul className="mt-2.5 space-y-1">
            {teams.map((t) => (
              <li key={t.team}>
                <button onClick={() => onPick(`${t.league}|${t.team}`)} className="flex w-full items-center gap-2 rounded-[4px] px-1 py-0.5 text-left text-caption text-muted hover:bg-surface-2 hover:text-fg">
                  <TeamBadge team={t.team} size={16} />
                  <span className="truncate">{tn(t.team)}</span>
                </button>
              </li>
            ))}
            {teams.length === 0 && <li className="text-micro text-subtle">Ningún equipo</li>}
          </ul>
        </div>
      ))}
    </div>
  )
}

export default function Styles() {
  const { data: s, error } = useApi<StylesData>(api.styles)
  const [params, setParams] = useSearchParams()
  useCrumbs([{ label: 'Estilos de juego' }])
  const seasons = useMemo(() => (s ? [...new Set(s.teams.map((t) => t.season))].sort() : []), [s])
  const rawSeason = params.get('temporada')
  const season: number | 'now' = !rawSeason || rawSeason === 'now' ? 'now' : Number(rawSeason)
  const league = params.get('liga') ?? 'SP1'
  const [highlight, setHighlight] = useState<ArchetypeKey | null>(null)
  const focus = params.get('equipo')
  const set = (k: string, v: string | null) => {
    const p = new URLSearchParams(params)
    if (v === null) p.delete(k)
    else p.set(k, v)
    setParams(p, { replace: true })
  }

  if (error) return <ErrorState message="No se pudieron cargar los estilos." hint="Genera los datos con python -m futdata.styles y recarga." />
  if (!s) return <Skeleton className="h-[720px] w-full" />

  const both = s.explained[0] + s.explained[1]
  const top = s.movers[0]
  const focusRows = focus ? s.teams.filter((t) => `${t.league}|${t.team}` === focus).sort((a, b) => a.season - b.season) : []
  const focusNow = focus ? s.current.find((t) => `${t.league}|${t.team}` === focus) : undefined

  return (
    <>
      <PageHeader
        title="Estilos de juego"
        sub={`${s.n} equipos-temporada, 19 métricas y dos ejes que explican el ${pct(both)} de cómo juegan`}
      />

      <Chapter
        title="Un mapa de cómo juega cada equipo"
        lead={
          <>
            Cada escudo es un equipo. Cuanto más a la derecha, más balón y más dominio; cuanto más arriba, más centros, juego aéreo y balón
            parado. El color del aro es su familia de estilo, y debajo del mapa están los equipos agrupados por familia. En «Ahora», cada
            equipo es la media de sus últimos {s.window} partidos. Pasa el ratón por un escudo para ver de dónde viene, o púlsalo para ver toda
            su trayectoria.
          </>
        }
      >
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <Segmented
            id="st-season"
            value={season}
            onChange={(v) => set('temporada', v === 'now' ? null : String(v))}
            options={[...seasons.map((x) => ({ value: x as number | 'now', label: seasonLabel(x) })), { value: 'now' as const, label: 'Ahora' }]}
          />
          <Segmented
            id="st-league"
            value={league}
            onChange={(v) => set('liga', v === 'SP1' ? null : v)}
            options={[{ value: 'all', label: 'Todas' }, ...LEAGUE_ORDER.map((c) => ({ value: c, label: LEAGUES[c].short }))]}
          />
        </div>
        <div className="mb-3 flex flex-wrap gap-1.5">
          {s.archetypes.slice().sort((a, b) => b.pc[0] - a.pc[0]).map((a) => (
            <button
              key={a.key}
              onMouseEnter={() => setHighlight(a.key)}
              onMouseLeave={() => setHighlight(null)}
              onClick={() => setHighlight(highlight === a.key ? null : a.key)}
              title={a.description}
              className="flex h-7 items-center gap-1.5 rounded-full bg-surface-2 px-2.5 text-caption text-muted transition-colors hover:bg-surface-3 hover:text-fg"
            >
              <span className="size-2.5 rounded-full border-2" style={{ borderColor: a.color }} />
              {a.name}
            </button>
          ))}
          <span className="ml-1 self-center text-caption text-subtle">El aro de cada escudo indica su familia de estilo</span>
        </div>
        <Panel className="overflow-hidden">
          <StyleMap styles={s} season={season} league={league} focus={focus} onFocus={(k) => set('equipo', k)} highlight={highlight} />
          {focusRows.length > 0 && (
            <div className="flex flex-wrap items-center gap-x-6 gap-y-2 border-t border-line px-4 py-3 text-label">
              <span className="flex items-center gap-2 font-medium">
                <TeamBadge team={focusRows[0].team} size={18} /> {tn(focusRows[0].team)}
              </span>
              {focusRows.map((r) => (
                <span key={r.season} className="flex items-center gap-1.5 text-caption">
                  <span className="num text-subtle">{seasonLabel(r.season)}</span>
                  <span style={{ color: archetypeOf(s, r.archetype).color }}>{archetypeOf(s, r.archetype).name}</span>
                </span>
              ))}
              {focusNow && (
                <span className="flex items-center gap-1.5 text-caption">
                  <span className="text-subtle">ahora</span>
                  <span className="font-medium" style={{ color: archetypeOf(s, focusNow.archetype).color }}>{archetypeOf(s, focusNow.archetype).name}</span>
                </span>
              )}
              <Link
                to={`/equipos/${focusRows[0].league}/${encodeURIComponent(focusRows[0].team)}?tab=estilo`}
                className="ml-auto text-caption text-muted hover:text-fg"
              >
                Ver el equipo →
              </Link>
            </div>
          )}
        </Panel>
        <ArchetypeColumns s={s} season={season} league={league} onPick={(k) => set('equipo', k)} onHover={setHighlight} />
      </Chapter>

      <Chapter
        title="Lo que ha cambiado este verano"
        lead={
          <>
            Comparando sus últimos {s.window} partidos con cómo acabó la temporada pasada. Con tan pocos partidos de esta temporada, las
            diferencias pequeñas pueden ser ruido; las grandes suelen tener nombre propio: entrenador nuevo, salidas o fichajes.
          </>
        }
      >
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
          {s.current
            .filter((c) => c.prev)
            .map((c) => ({ c, d: Math.hypot(c.pc1 - c.prev!.pc1, c.pc2 - c.prev!.pc2) }))
            .sort((a, b) => b.d - a.d)
            .slice(0, 9)
            .map(({ c, d }, i) => {
              const before = archetypeOf(s, c.prev!.archetype)
              const after = archetypeOf(s, c.archetype)
              const dx = c.pc1 - c.prev!.pc1
              const dy = c.pc2 - c.prev!.pc2
              const words = [
                Math.abs(dx) > 0.6 ? (dx > 0 ? 'más dominio' : 'menos dominio') : null,
                Math.abs(dy) > 0.6 ? (dy > 0 ? 'más juego por fuera y físico' : 'menos juego por fuera') : null,
              ].filter(Boolean)
              return (
                <motion.button
                  key={c.team}
                  initial={{ opacity: 0, y: 8 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true }}
                  transition={{ duration: 0.4, delay: i * 0.04, ease }}
                  onClick={() => {
                    const p = new URLSearchParams(params)
                    p.delete('temporada')
                    p.set('equipo', `${c.league}|${c.team}`)
                    setParams(p, { replace: true })
                    window.scrollTo({ top: 0, behavior: 'smooth' })
                  }}
                  className="flex items-center gap-3 rounded-panel bg-surface-1 p-4 text-left transition-[background-color,transform] hover:bg-surface-2 active:scale-[0.99]"
                >
                  <TeamBadge team={c.team} size={30} />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-label font-semibold">{tn(c.team)}</span>
                    <span className="block text-caption">
                      <span style={{ color: before.color }}>{before.name}</span>
                      <span className="text-subtle"> → </span>
                      <span style={{ color: after.color }}>{after.name}</span>
                    </span>
                    <span className="block text-micro text-subtle">
                      {words.length ? words.join(' · ') : 'mismo arquetipo, otro matiz'} · {c.this_season} partidos de 26/27{c.short_sample ? ' · muestra corta' : ''}
                    </span>
                  </span>
                  <span className="num text-caption text-muted">{num(d, 1)}</span>
                </motion.button>
              )
            })}
        </div>
      </Chapter>

      <Chapter
        title="Seis maneras de jugar"
        lead="Agrupando a los equipos por parecido aparecen seis familias. Las barras muestran en qué se separa cada una de la media: a la derecha, más que el resto; a la izquierda, menos."
      >
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          {s.archetypes
            .slice()
            .sort((a, b) => b.pc[0] - a.pc[0])
            .map((a, i) => (
              <motion.div
                key={a.key}
                initial={{ opacity: 0, y: 12 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.5, delay: i * 0.06, ease }}
                className="relative overflow-hidden rounded-panel bg-surface-1 p-5"
              >
                <div className="absolute inset-x-0 top-0 h-1" style={{ background: a.color }} />
                <div className="flex items-baseline justify-between">
                  <h3 className="text-[17px] font-semibold" style={{ color: a.color }}>{a.name}</h3>
                  <span className="num text-caption text-subtle">{a.size} equipos-temp.</span>
                </div>
                <p className="mt-2 min-h-[60px] text-label leading-5 text-muted">{a.description}</p>
                <div className="mt-4">
                  <Fingerprint styles={s} values={a.centroid} color={a.color} />
                </div>
                <div className="mt-4 flex flex-wrap gap-1.5 border-t border-line pt-3">
                  {a.typical.slice(0, 5).map((t) => (
                    <button
                      key={`${t.team}${t.season}`}
                      onClick={() => {
                        const p = new URLSearchParams(params)
                        p.set('temporada', String(t.season))
                        p.set('equipo', `${t.league}|${t.team}`)
                        setParams(p, { replace: true })
                        window.scrollTo({ top: 0, behavior: 'smooth' })
                      }}
                      className="flex h-7 items-center gap-1.5 rounded-full bg-surface-2 px-2 text-caption text-muted transition-colors hover:bg-surface-3 hover:text-fg"
                    >
                      <TeamBadge team={t.team} size={14} />
                      {tn(t.team)} <span className="num text-subtle">{String(t.season % 100).padStart(2, '0')}</span>
                    </button>
                  ))}
                </div>
              </motion.div>
            ))}
        </div>
      </Chapter>

      <Chapter
        title="Quién cambió de piel"
        lead={
          top ? (
            <>
              El mayor salto de una temporada a la siguiente es el de {tn(top.team)} entre {seasonLabel(top.from)} y {seasonLabel(top.to)}:
              de «{archetypeOf(s, top.archetypes[0]).name}» a «{archetypeOf(s, top.archetypes[1]).name}». Detrás de casi todos estos cambios hay un
              entrenador nuevo o un proyecto distinto.
            </>
          ) : null
        }
      >
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {s.movers.slice(0, 8).map((mv) => {
            const a = archetypeOf(s, mv.archetypes[0])
            const b = archetypeOf(s, mv.archetypes[1])
            return (
              <Link
                key={`${mv.team}${mv.from}`}
                to={`/estilos?temporada=${mv.to}&equipo=${encodeURIComponent(`${mv.league}|${mv.team}`)}`}
                onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}
                className="group rounded-panel bg-surface-1 p-4 transition-colors hover:bg-surface-2"
              >
                <div className="flex items-center gap-2">
                  <TeamBadge team={mv.team} size={20} />
                  <span className="truncate text-label font-semibold">{tn(mv.team)}</span>
                  <span className="num ml-auto text-micro text-subtle">{seasonLabel(mv.from)} → {String(mv.to % 100).padStart(2, '0')}</span>
                </div>
                <div className="my-2">
                  <MiniMove styles={s} move={mv} />
                </div>
                <div className="text-caption">
                  <span style={{ color: a.color }}>{a.name}</span>
                  <span className="text-subtle"> → </span>
                  <span style={{ color: b.color }}>{b.name}</span>
                </div>
                <div className="num text-micro text-subtle">desplazamiento {num(mv.distance, 1)}</div>
              </Link>
            )
          })}
        </div>
      </Chapter>

      <div className="mt-20">
        <Chapter
          title="Cada liga, su acento"
          lead="Posición media de los equipos de cada liga en los dos ejes, todas las temporadas juntas. Las diferencias entre ligas son mucho menores que entre equipos: la mayor parte del estilo es del club, no del campeonato."
        >
          <Panel className="p-4">
            <LeagueAccents s={s} />
          </Panel>
        </Chapter>

        </div>
        <div className="mt-20">
        <Chapter
          title="Qué significa cada eje"
          lead="Cuánto pesa cada métrica en los dos ejes del mapa (cargas de la PCA). Las métricas se estandarizan antes, así que se comparan entre sí."
        >
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            {s.axes.map((ax) => {
              const items = Object.entries(ax.loadings).sort((a, b) => b[1] - a[1])
              const max = Math.max(...items.map(([, v]) => Math.abs(v)))
              return (
                <Panel key={ax.name}>
                  <PanelHeader title={ax.name} sub={`${pct(ax.explained)} de la varianza`} />
                  <ul className="space-y-1 p-4">
                    {items.map(([k, v]) => (
                      <li key={k} className="grid grid-cols-[120px_minmax(0,1fr)] items-center gap-3 text-caption">
                        <span className="truncate text-muted">{s.features.find((f) => f.key === k)?.label}</span>
                        <span className="relative h-1.5">
                          <span className="absolute -inset-y-0.5 left-1/2 w-px bg-line-strong" />
                          <span
                            className="absolute inset-y-0 rounded-full"
                            style={{ background: v >= 0 ? 'var(--accent)' : 'var(--text-subtle)', [v >= 0 ? 'left' : 'right']: '50%', width: `${(Math.abs(v) / max) * 50}%` }}
                          />
                        </span>
                      </li>
                    ))}
                  </ul>
                </Panel>
              )
            })}
          </div>
        </Chapter>
      </div>

      <p className="mt-16 max-w-[720px] text-caption leading-5 text-subtle">
        Método: medias por partido de 19 métricas de PitchAPI por equipo y temporada (mínimo 8 partidos), estandarizadas sobre las cinco ligas y
        todas las temporadas; PCA para los dos ejes y k-means (k = 6) sobre las 19 métricas para los arquetipos. Los nombres de los arquetipos se
        asignan por reglas sobre los centroides. «Pasividad sin balón» es una aproximación al PPDA: pases del rival por entrada, intercepción o
        falta propia.
      </p>
    </>
  )
}
