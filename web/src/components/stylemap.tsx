import { scaleLinear } from 'd3-scale'
import { AnimatePresence, motion } from 'motion/react'
import { useLayoutEffect, useMemo, useRef, useState } from 'react'
import type { ArchetypeKey, StyleCurrent, Styles, StyleTeam } from '../lib/api'
import { teamCrest, teamName as tn } from '../lib/api'
import { LEAGUES, seasonLabel } from '../lib/format'
import { cx } from './ui'

function useSize<T extends HTMLElement>(): [React.RefObject<T | null>, number] {
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

export function archetypeOf(s: Styles, key: ArchetypeKey) {
  return s.archetypes.find((a) => a.key === key)!
}

/** Escalas comunes a todos los mapas para que las posiciones sean comparables. */
export function useExtent(s: Styles) {
  return useMemo(() => {
    const xs = s.teams.map((t) => t.pc1)
    const ys = s.teams.map((t) => t.pc2)
    const pad = (a: number[]) => [Math.min(...a) - 0.6, Math.max(...a) + 0.6] as [number, number]
    return { x: pad(xs), y: pad(ys) }
  }, [s])
}

/* ---------------------------------------------------------------- mapa principal */

export function StyleMap({
  styles,
  season,
  league,
  focus,
  onFocus,
  height = 620,
  highlight = null,
}: {
  styles: Styles
  season: number | 'now'
  league: string
  focus: string | null
  onFocus: (key: string | null) => void
  height?: number
  highlight?: ArchetypeKey | null
}) {
  const [ref, width] = useSize<HTMLDivElement>()
  const [hover, setHover] = useState<StyleTeam | StyleCurrent | null>(null)
  const ext = useExtent(styles)
  const isNow = season === 'now'
  const m = { t: 28, r: 36, b: 40, l: 36 }
  const pool0: (StyleTeam | StyleCurrent)[] = isNow ? styles.current : styles.teams.filter((t) => t.season === season)
  const shown0 = pool0.filter((t) => league === 'all' || t.league === league)
  // Zoom a los equipos visibles (con el origen siempre dentro, para que los cuadrantes tengan sentido)
  const span = (vals: number[], full: [number, number]): [number, number] => {
    if (!vals.length) return full
    const lo = Math.min(0, ...vals)
    const hi = Math.max(0, ...vals)
    const pad = Math.max((hi - lo) * 0.12, 0.6)
    return [lo - pad, hi + pad]
  }
  const x = scaleLinear().domain(span(shown0.map((t) => t.pc1), ext.x)).range([m.l, Math.max(m.l + 1, width - m.r)])
  const y = scaleLinear().domain(span(shown0.map((t) => t.pc2), ext.y)).range([height - m.b - 30, m.t + 40])
  const color = (k: ArchetypeKey) => archetypeOf(styles, k).color

  const pool: (StyleTeam | StyleCurrent)[] = isNow ? styles.current : styles.teams.filter((t) => t.season === season)
  const visible = pool.filter((t) => league === 'all' || t.league === league)
  const focusTeam: (StyleTeam | StyleCurrent)[] = focus
    ? [
        ...styles.teams.filter((t) => `${t.league}|${t.team}` === focus).sort((a, b) => a.season - b.season),
        ...(isNow ? styles.current.filter((t) => `${t.league}|${t.team}` === focus) : []),
      ]
    : []
  const size = width < 700 ? 22 : 30
  // Cuadrantes con nombre: qué tipo de equipo vive en cada esquina del mapa
  const quadrants = [
    { x: m.l + 4, y: m.t + 6, anchor: 'start' as const, title: 'Directos y físicos', sub: 'poco balón · juego aéreo y balón parado' },
    { x: width - m.r - 4, y: m.t + 6, anchor: 'end' as const, title: 'Dominan y cargan el área', sub: 'mucho balón · centros y área' },
    { x: m.l + 4, y: height - m.b - 22, anchor: 'start' as const, title: 'Repliegue y sufrimiento', sub: 'poco balón · conceden mucho' },
    { x: width - m.r - 4, y: height - m.b - 22, anchor: 'end' as const, title: 'Dominan con el pase', sub: 'mucho balón · pase corto y paciencia' },
  ]
  const trail = (hover && 'prev' in hover && hover.prev ? hover : null) as StyleCurrent | null

  return (
    <div ref={ref} className="relative w-full select-none" style={{ height }}>
      {width > 0 && (
        <svg width={width} height={height} className="block" onClick={() => onFocus(null)}>
          <defs>
            <pattern id="dots" width={22} height={22} patternUnits="userSpaceOnUse">
              <circle cx={1} cy={1} r={0.8} fill="var(--border-strong)" />
            </pattern>
          </defs>
          <rect x={0} y={0} width={width} height={height} fill="url(#dots)" opacity={0.45} />

          {/* Cuadrantes */}
          {quadrants.map((q) => (
            <g key={q.title} pointerEvents="none">
              <text x={q.x} y={q.y + 12} textAnchor={q.anchor} fontSize={13} fontWeight={600} fill="var(--text-muted)">{q.title}</text>
              <text x={q.x} y={q.y + 28} textAnchor={q.anchor} fontSize={11} fill="var(--text-subtle)">{q.sub}</text>
            </g>
          ))}

          {/* Ejes con nombre en lenguaje llano */}
          <line x1={x(0)} x2={x(0)} y1={m.t} y2={height - m.b} stroke="var(--border-strong)" />
          <line x1={m.l} x2={width - m.r} y1={y(0)} y2={y(0)} stroke="var(--border-strong)" />
          <g pointerEvents="none" fontSize={11} fill="var(--text-subtle)">
            <text x={m.l} y={y(0) - 8}>← menos balón</text>
            <text x={width - m.r} y={y(0) - 8} textAnchor="end">más balón y dominio →</text>
            <text x={x(0) + 8} y={m.t + 4}>↑ más centros y juego aéreo</text>
            <text x={x(0) + 8} y={height - m.b + 4}>↓ más pase corto</text>
          </g>

          {/* Trayectoria del equipo elegido */}
          {focusTeam.length > 1 && (
            <g pointerEvents="none">
              <motion.path
                d={focusTeam.map((t, i) => `${i ? 'L' : 'M'}${x(t.pc1)},${y(t.pc2)}`).join('')}
                fill="none"
                stroke="var(--text)"
                strokeWidth={1.5}
                strokeDasharray="4 4"
                initial={{ pathLength: 0 }}
                animate={{ pathLength: 1 }}
                transition={{ duration: 0.9 }}
              />
              {focusTeam.map((t) => (
                <g key={'prev' in t ? 'now' : t.season}>
                  <circle cx={x(t.pc1)} cy={y(t.pc2)} r={4.5} fill={color(t.archetype)} stroke="var(--bg)" strokeWidth={1.5} />
                  <text x={x(t.pc1) + 9} y={y(t.pc2) - 9} fontSize={11} fontWeight={500} fill="var(--text)" stroke="var(--bg)" strokeWidth={3} style={{ paintOrder: 'stroke' }} className="num">
                    {'prev' in t ? 'ahora' : seasonLabel(t.season)}
                  </text>
                </g>
              ))}
            </g>
          )}

          {/* Al señalar un equipo en «Ahora»: de dónde viene (final de la temporada anterior) */}
          {isNow && !focus && trail && (
            <g pointerEvents="none">
              <line x1={x(trail.prev!.pc1)} y1={y(trail.prev!.pc2)} x2={x(trail.pc1)} y2={y(trail.pc2)} stroke="var(--text)" strokeWidth={1.5} strokeDasharray="4 4" />
              <circle cx={x(trail.prev!.pc1)} cy={y(trail.prev!.pc2)} r={5} fill="var(--surface-1)" stroke="var(--text-muted)" strokeWidth={1.5} />
              <text x={x(trail.prev!.pc1) + 9} y={y(trail.prev!.pc2) + 4} fontSize={11} fill="var(--text-muted)" stroke="var(--bg)" strokeWidth={3} style={{ paintOrder: 'stroke' }} className="num">
                {seasonLabel(trail.prev!.season)}
              </text>
            </g>
          )}

          {/* Equipos de la temporada: escudos */}
          {visible.map((t) => {
            const key = `${t.league}|${t.team}`
            const crest = teamCrest(t.team)
            const dim = (focus && focus !== key) || (hover && hover !== t) || (highlight && t.archetype !== highlight)
            return (
              <motion.g
                key={key}
                initial={false}
                animate={{ x: x(t.pc1), y: y(t.pc2), opacity: dim ? 0.25 : 1 }}
                transition={{ type: 'spring', stiffness: 120, damping: 20 }}
                onMouseEnter={() => setHover(t)}
                onMouseLeave={() => setHover(null)}
                onClick={(e) => {
                  e.stopPropagation()
                  onFocus(focus === key ? null : key)
                }}
                className="cursor-pointer"
              >
                <circle r={size / 2 + 3} fill="var(--surface-1)" stroke={color(t.archetype)} strokeWidth={2} />
                {crest ? (
                  <image href={crest} x={-size / 2 + 2} y={-size / 2 + 2} width={size - 4} height={size - 4} />
                ) : (
                  <circle r={3} fill={color(t.archetype)} />
                )}
              </motion.g>
            )
          })}
        </svg>
      )}
      <AnimatePresence>
        {hover && width > 0 && (
          <motion.div
            key={`${hover.league}${hover.team}`}
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.12 }}
            className="pointer-events-none absolute z-10 w-64 rounded-panel border border-line-strong bg-surface-2 p-3 float-shadow"
            style={{
              left: Math.min(Math.max(x(hover.pc1) + 20, 8), width - 272),
              top: Math.min(Math.max(y(hover.pc2) - 40, 8), height - 190),
            }}
          >
            <div className="flex items-center justify-between gap-2">
              <span className="truncate text-label font-semibold">{tn(hover.team)}</span>
              <span className="text-micro text-subtle">{LEAGUES[hover.league].short} · {'prev' in hover ? `últimos ${hover.matches}` : seasonLabel(hover.season)}</span>
            </div>
            <div className="mt-1 text-caption font-medium" style={{ color: color(hover.archetype) }}>
              {archetypeOf(styles, hover.archetype).name}
              {'prev' in hover && hover.prev && hover.prev.archetype !== hover.archetype && (
                <span className="text-subtle"> · antes {archetypeOf(styles, hover.prev.archetype).name.toLowerCase()}</span>
              )}
            </div>
            {'prev' in hover && (
              <div className="mt-0.5 text-micro text-subtle">
                {hover.this_season} de {hover.matches} partidos son de esta temporada{hover.short_sample ? ' · muestra corta' : ''}
              </div>
            )}
            <div className="mt-2.5 space-y-1">
              {topTraits(styles, hover).map((t) => (
                <div key={t.key} className="flex items-center gap-2 text-caption">
                  <span className="w-28 truncate text-muted">{t.label}</span>
                  <span className="relative h-1.5 flex-1 rounded-full bg-surface-3">
                    <span className="absolute inset-y-0 left-1/2 w-px bg-line-strong" />
                    <span
                      className="absolute inset-y-0 rounded-full"
                      style={{ background: color(hover.archetype), [t.z >= 0 ? 'left' : 'right']: '50%', width: `${Math.min(Math.abs(t.z), 2.5) / 2.5 * 50}%` }}
                    />
                  </span>
                </div>
              ))}
            </div>
            <div className="mt-2.5 border-t border-line pt-2 text-micro text-subtle">
              Se parece a {hover.similar.map((s) => tn(s.team)).join(', ')}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

/** Los 5 rasgos en que más se aleja de la media (en desviaciones típicas). */
export function topTraits(s: Styles, t: StyleTeam) {
  return s.features
    .map((f) => ({ key: f.key, label: f.label, z: t.z[f.key] }))
    .sort((a, b) => Math.abs(b.z) - Math.abs(a.z))
    .slice(0, 5)
}

/* ---------------------------------------------------------------- minimapa (cambios de estilo) */

export function MiniMove({ styles, move }: { styles: Styles; move: Styles['movers'][number] }) {
  const ext = useExtent(styles)
  const W = 220
  const H = 140
  const x = scaleLinear().domain(ext.x).range([10, W - 10])
  const y = scaleLinear().domain(ext.y).range([H - 10, 10])
  const [a, b] = move.path
  const ca = archetypeOf(styles, move.archetypes[0]).color
  const cb = archetypeOf(styles, move.archetypes[1]).color
  const id = `arrow-${move.team}-${move.from}`.replace(/\W/g, '')
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="block w-full">
      <defs>
        <marker id={id} viewBox="0 0 10 10" refX={8} refY={5} markerWidth={7} markerHeight={7} orient="auto-start-reverse">
          <path d="M0,0 L10,5 L0,10 z" fill={cb} />
        </marker>
      </defs>
      {styles.teams.filter((t) => t.season === move.to).map((t, i) => (
        <circle key={i} cx={x(t.pc1)} cy={y(t.pc2)} r={1.6} fill="var(--border-strong)" />
      ))}
      <line x1={x(0)} x2={x(0)} y1={0} y2={H} stroke="var(--border)" strokeDasharray="2 4" />
      <line x1={0} x2={W} y1={y(0)} y2={y(0)} stroke="var(--border)" strokeDasharray="2 4" />
      <motion.line
        x1={x(a[0])}
        y1={y(a[1])}
        initial={{ x2: x(a[0]), y2: y(a[1]) }}
        whileInView={{ x2: x(b[0]), y2: y(b[1]) }}
        viewport={{ once: true }}
        transition={{ duration: 1, ease: [0.16, 1, 0.3, 1] }}
        stroke={cb}
        strokeWidth={2}
        markerEnd={`url(#${id})`}
      />
      <circle cx={x(a[0])} cy={y(a[1])} r={4} fill={ca} stroke="var(--surface-1)" strokeWidth={1.5} />
    </svg>
  )
}

/* ---------------------------------------------------------------- huella del arquetipo */

export function Fingerprint({ styles, values, color, keys }: { styles: Styles; values: Record<string, number>; color: string; keys?: string[] }) {
  const feats = (keys ?? ['posesion', 'directo', 'xg', 'xg_contra', 'ppda', 'duelos_aereos', 'balon_parado', 'tiros_lejanos'])
    .map((k) => styles.features.find((f) => f.key === k)!)
  return (
    <div className="space-y-1.5">
      {feats.map((f, i) => {
        const z = values[f.key]
        return (
          <div key={f.key} className="grid grid-cols-[110px_minmax(0,1fr)] items-center gap-3 text-caption">
            <span className="truncate text-muted">{f.label}</span>
            <span className="relative h-2 rounded-full bg-surface-3">
              <span className="absolute -inset-y-0.5 left-1/2 w-px bg-line-strong" />
              <motion.span
                className={cx('absolute inset-y-0 rounded-full')}
                style={{ background: color, [z >= 0 ? 'left' : 'right']: '50%' }}
                initial={{ width: 0 }}
                whileInView={{ width: `${(Math.min(Math.abs(z), 2) / 2) * 50}%` }}
                viewport={{ once: true }}
                transition={{ duration: 0.6, delay: i * 0.03, ease: [0.16, 1, 0.3, 1] }}
              />
            </span>
          </div>
        )
      })}
    </div>
  )
}

/* ---------------------------------------------------------------- estilo de un equipo */

export function TeamStyleCard({ styles, league, team, season }: { styles: Styles; league: string; team: string; season: number }) {
  const row = styles.teams.find((t) => t.league === league && t.team === team && t.season === season)
    ?? styles.teams.filter((t) => t.league === league && t.team === team).sort((a, b) => b.season - a.season)[0]
  const now = styles.current.find((t) => t.league === league && t.team === team)
  const useNow = !!now && season >= now.season
  if (!row && !now) return null
  const shown = (useNow ? now : row)!
  const a = archetypeOf(styles, shown.archetype)
  const history = styles.teams.filter((t) => t.league === league && t.team === team).sort((x, y) => x.season - y.season)
  return (
    <div className="grid grid-cols-1 gap-6 xl:grid-cols-[360px_minmax(0,1fr)]">
      <div className="relative overflow-hidden rounded-panel bg-surface-1 p-5">
        <div className="absolute inset-x-0 top-0 h-1" style={{ background: a.color }} />
        <div className="relative">
          <div className="text-caption text-subtle">
            {useNow ? `Ahora · últimos ${now!.matches} partidos (${now!.this_season} de esta temporada)` : `Arquetipo · ${seasonLabel(shown.season)}`}
          </div>
          <div className="mt-1 text-[22px] font-semibold tracking-[-0.02em]" style={{ color: a.color }}>{a.name}</div>
          <p className="mt-2 text-label leading-5 text-muted">{a.description}</p>
          <div className="mt-5 text-caption text-subtle">En qué se sale de la media</div>
          <div className="mt-2">
            <Fingerprint styles={styles} values={shown.z} color={a.color} keys={topTraits(styles, shown).map((t) => t.key)} />
          </div>
          <div className="mt-5 text-caption text-subtle">{useNow ? 'Se parece a (temporada pasada)' : 'Los más parecidos esta temporada'}</div>
          <ul className="mt-2 space-y-1.5">
            {shown.similar.map((s) => (
              <li key={s.team} className="text-label">
                <a href={`/equipos/${s.league}/${encodeURIComponent(s.team)}?tab=estilo`} className="text-fg hover:underline">{tn(s.team)}</a>
                <span className="ml-1.5 text-micro text-subtle">{LEAGUES[s.league].short}</span>
              </li>
            ))}
          </ul>
          {(history.length > 1 || now) && (
            <>
              <div className="mt-5 text-caption text-subtle">Temporada a temporada</div>
              <ol className="mt-2 space-y-1">
                {history.map((h) => (
                  <li key={h.season} className="flex items-center gap-2 text-caption">
                    <span className="num w-12 text-subtle">{seasonLabel(h.season)}</span>
                    <span className="size-2 rounded-full" style={{ background: archetypeOf(styles, h.archetype).color }} />
                    <span className="text-muted">{archetypeOf(styles, h.archetype).name}</span>
                  </li>
                ))}
                {now && (
                  <li className="flex items-center gap-2 text-caption">
                    <span className="w-12 text-subtle">ahora</span>
                    <span className="size-2 rounded-full" style={{ background: archetypeOf(styles, now.archetype).color }} />
                    <span className="font-medium text-fg">{archetypeOf(styles, now.archetype).name}</span>
                  </li>
                )}
              </ol>
            </>
          )}
        </div>
      </div>
      <div className="overflow-hidden rounded-panel bg-surface-1">
        <StyleMap styles={styles} season={useNow ? 'now' : shown.season} league={league} focus={`${league}|${team}`} onFocus={() => {}} height={520} />
      </div>
    </div>
  )
}
