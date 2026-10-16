import { extent } from 'd3-array'
import { scaleLinear, scaleTime } from 'd3-scale'
import { area, curveMonotoneX, line } from 'd3-shape'
import { motion } from 'motion/react'
import { useLayoutEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { num } from '../lib/format'

/** Ancho real del contenedor para dibujar a escala 1:1 (texto nítido, sin viewBox estirado). */
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

/* ---------------------------------------------------------------- serie temporal */

export type Series = {
  key: string
  label: string
  color: string
  values: (number | null)[]
  dashed?: boolean
  area?: boolean
}

export function TimeChart({
  dates,
  series,
  height = 220,
  format = (v: number) => num(v),
  baseline,
  tooltipTitle,
}: {
  dates: Date[]
  series: Series[]
  height?: number
  format?: (v: number) => string
  baseline?: { value: number; label: string }
  tooltipTitle?: (i: number) => ReactNode
}) {
  const [ref, width] = useWidth<HTMLDivElement>()
  const [hover, setHover] = useState<number | null>(null)
  const m = { t: 12, r: 12, b: 26, l: 40 }
  const all = series.flatMap((s) => s.values.filter((v): v is number => v !== null))
  const [lo, hi] = extent(all.concat(baseline ? [baseline.value] : [])) as [number, number]
  const pad = (hi - lo) * 0.12 || 1
  const x = scaleTime().domain(extent(dates) as [Date, Date]).range([m.l, Math.max(m.l + 1, width - m.r)])
  const y = scaleLinear().domain([lo - pad, hi + pad]).nice(4).range([height - m.b, m.t])

  const paths = useMemo(
    () =>
      series.map((s) => {
        const pts = s.values.map((v, i) => [dates[i], v] as const)
        const ln = line<readonly [Date, number | null]>()
          .defined((d) => d[1] !== null)
          .x((d) => x(d[0]))
          .y((d) => y(d[1] as number))
          .curve(curveMonotoneX)
        const ar = area<readonly [Date, number | null]>()
          .defined((d) => d[1] !== null)
          .x((d) => x(d[0]))
          .y0(y.range()[0])
          .y1((d) => y(d[1] as number))
          .curve(curveMonotoneX)
        return { s, d: ln(pts) ?? '', a: s.area ? ar(pts) ?? '' : '' }
      }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [series, dates, width, height],
  )

  const onMove = (e: React.MouseEvent<SVGSVGElement>) => {
    const rect = e.currentTarget.getBoundingClientRect()
    const t = x.invert(e.clientX - rect.left).getTime()
    let best = 0
    dates.forEach((d, i) => {
      if (Math.abs(d.getTime() - t) < Math.abs(dates[best].getTime() - t)) best = i
    })
    setHover(best)
  }

  return (
    <div ref={ref} className="relative w-full" style={{ height }}>
      {width > 0 && (
        <svg width={width} height={height} onMouseMove={onMove} onMouseLeave={() => setHover(null)} className="block">
          {y.ticks(4).map((t) => (
            <g key={t}>
              <line x1={m.l} x2={width - m.r} y1={y(t)} y2={y(t)} stroke="var(--border)" />
              <text x={m.l - 8} y={y(t) + 4} textAnchor="end" fontSize={11} fill="var(--text-subtle)" className="num">
                {format(t)}
              </text>
            </g>
          ))}
          {x.ticks(Math.max(2, Math.floor(width / 120))).map((t) => (
            <text key={+t} x={x(t)} y={height - 6} textAnchor="middle" fontSize={11} fill="var(--text-subtle)">
              {t.toLocaleDateString('es-ES', { month: 'short', year: '2-digit' }).replace('.', '')}
            </text>
          ))}
          {baseline && (
            <g>
              <line x1={m.l} x2={width - m.r} y1={y(baseline.value)} y2={y(baseline.value)} stroke="var(--text-subtle)" strokeDasharray="2 4" />
              <text x={width - m.r} y={y(baseline.value) - 5} textAnchor="end" fontSize={11} fill="var(--text-subtle)">
                {baseline.label}
              </text>
            </g>
          )}
          {paths.map(({ s, a }) => a && <path key={`a-${s.key}`} d={a} fill={s.color} opacity={0.08} />)}
          {paths.map(({ s, d }) => (
            <motion.path
              key={s.key}
              d={d}
              fill="none"
              stroke={s.color}
              strokeWidth={1.75}
              strokeDasharray={s.dashed ? '4 4' : undefined}
              initial={{ pathLength: 0 }}
              animate={{ pathLength: 1 }}
              transition={{ duration: 0.7, ease: [0.16, 1, 0.3, 1] }}
            />
          ))}
          {hover !== null && (
            <g>
              <line x1={x(dates[hover])} x2={x(dates[hover])} y1={m.t} y2={height - m.b} stroke="var(--border-strong)" />
              {series.map((s) =>
                s.values[hover] !== null ? (
                  <circle key={s.key} cx={x(dates[hover])} cy={y(s.values[hover] as number)} r={3.5} fill="var(--surface-1)" stroke={s.color} strokeWidth={2} />
                ) : null,
              )}
            </g>
          )}
        </svg>
      )}
      {hover !== null && width > 0 && (
        <div
          className="pointer-events-none absolute top-1 z-10 min-w-40 rounded-ctl border border-line-strong bg-surface-2 px-3 py-2 float-shadow"
          style={{
            left: Math.min(Math.max(x(dates[hover]) + 12, 0), width - 180),
          }}
        >
          <div className="mb-1 text-caption text-subtle">
            {tooltipTitle ? tooltipTitle(hover) : dates[hover].toLocaleDateString('es-ES', { day: 'numeric', month: 'short', year: 'numeric' })}
          </div>
          {series.map((s) => (
            <div key={s.key} className="flex items-center justify-between gap-4 text-caption">
              <span className="flex items-center gap-1.5 text-muted">
                <span className="h-[2px] w-2.5 rounded-full" style={{ background: s.color }} />
                {s.label}
              </span>
              <span className="num text-fg">{s.values[hover] !== null ? format(s.values[hover] as number) : '–'}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export function Legend({ items }: { items: { label: string; color: string; dashed?: boolean }[] }) {
  return (
    <div className="flex flex-wrap gap-4 text-caption text-muted">
      {items.map((i) => (
        <span key={i.label} className="flex items-center gap-1.5">
          <svg width={14} height={4}>
            <line x1={0} x2={14} y1={2} y2={2} stroke={i.color} strokeWidth={2} strokeDasharray={i.dashed ? '3 2' : undefined} />
          </svg>
          {i.label}
        </span>
      ))}
    </div>
  )
}

/* ---------------------------------------------------------------- dispersión */

export type Point = { id: string; label: string; x: number; y: number; highlight?: boolean; image?: string | null }

export function Scatter({
  points,
  xLabel,
  yLabel,
  height = 360,
  invertY = false,
  onSelect,
}: {
  points: Point[]
  xLabel: string
  yLabel: string
  height?: number
  invertY?: boolean
  onSelect?: (id: string) => void
}) {
  const [ref, width] = useWidth<HTMLDivElement>()
  const [hover, setHover] = useState<string | null>(null)
  const m = { t: 16, r: 16, b: 36, l: 44 }
  const [x0, x1] = extent(points, (p) => p.x) as [number, number]
  const [y0, y1] = extent(points, (p) => p.y) as [number, number]
  const x = scaleLinear().domain([x0 - 0.1, x1 + 0.1]).nice(5).range([m.l, Math.max(m.l + 1, width - m.r)])
  const y = scaleLinear().domain(invertY ? [y1 + 0.1, y0 - 0.1] : [y0 - 0.1, y1 + 0.1]).nice(5).range([height - m.b, m.t])
  const mx = points.reduce((a, p) => a + p.x, 0) / points.length
  const my = points.reduce((a, p) => a + p.y, 0) / points.length
  return (
    <div ref={ref} className="relative w-full" style={{ height }}>
      {width > 0 && (
        <svg width={width} height={height} className="block">
          {x.ticks(5).map((t) => (
            <g key={`x${t}`}>
              <line x1={x(t)} x2={x(t)} y1={m.t} y2={height - m.b} stroke="var(--border)" />
              <text x={x(t)} y={height - m.b + 16} textAnchor="middle" fontSize={11} fill="var(--text-subtle)" className="num">{num(t, 1)}</text>
            </g>
          ))}
          {y.ticks(5).map((t) => (
            <g key={`y${t}`}>
              <line x1={m.l} x2={width - m.r} y1={y(t)} y2={y(t)} stroke="var(--border)" />
              <text x={m.l - 8} y={y(t) + 4} textAnchor="end" fontSize={11} fill="var(--text-subtle)" className="num">{num(t, 1)}</text>
            </g>
          ))}
          <line x1={x(mx)} x2={x(mx)} y1={m.t} y2={height - m.b} stroke="var(--border-strong)" strokeDasharray="3 4" />
          <line x1={m.l} x2={width - m.r} y1={y(my)} y2={y(my)} stroke="var(--border-strong)" strokeDasharray="3 4" />
          <text x={width - m.r} y={height - 4} textAnchor="end" fontSize={11} fill="var(--text-muted)">{xLabel} →</text>
          <text x={m.l} y={m.t - 4} fontSize={11} fill="var(--text-muted)">↑ {yLabel}</text>
          {points.map((p, i) => {
            const active = hover === p.id
            return (
              <motion.g
                key={p.id}
                initial={{ opacity: 0 }}
                animate={{ opacity: hover && !active ? 0.35 : 1 }}
                transition={{ duration: 0.3, delay: hover ? 0 : i * 0.012 }}
                onMouseEnter={() => setHover(p.id)}
                onMouseLeave={() => setHover(null)}
                onClick={() => onSelect?.(p.id)}
                className={onSelect ? 'cursor-pointer' : undefined}
              >
                {p.image ? (
                  <>
                    {/* Escudo en lugar de punto; un aro de acento marca los destacados */}
                    {p.highlight && <circle cx={x(p.x)} cy={y(p.y)} r={active ? 15 : 13} fill="none" stroke="var(--accent)" strokeWidth={2} />}
                    <image href={p.image} x={x(p.x) - (active ? 11 : 9)} y={y(p.y) - (active ? 11 : 9)} width={active ? 22 : 18} height={active ? 22 : 18} preserveAspectRatio="xMidYMid meet" />
                    {active && (
                      <text x={x(p.x) + 16} y={y(p.y) + 4} fontSize={12} fontWeight={600} fill="var(--text)">
                        {p.label}
                      </text>
                    )}
                  </>
                ) : (
                  <>
                    <circle cx={x(p.x)} cy={y(p.y)} r={active ? 6 : 4.5} fill={p.highlight ? 'var(--accent)' : 'var(--text-muted)'} stroke="var(--surface-1)" strokeWidth={1.5} />
                    <text x={x(p.x) + 8} y={y(p.y) + 4} fontSize={11} fill={active ? 'var(--text)' : 'var(--text-subtle)'}>
                      {p.label}
                    </text>
                  </>
                )}
              </motion.g>
            )
          })}
        </svg>
      )}
    </div>
  )
}

/* ---------------------------------------------------------------- calibración */

export type CalPoint = { p: number; freq: number; n: number; lo: number; hi: number }

export function Calibration({ model, market, height = 320 }: { model: CalPoint[]; market: CalPoint[]; height?: number }) {
  const [ref, width] = useWidth<HTMLDivElement>()
  const m = { t: 12, r: 12, b: 34, l: 40 }
  const histH = 44
  const plotH = height - histH - 10
  const x = scaleLinear().domain([0, 0.8]).range([m.l, Math.max(m.l + 1, width - m.r)])
  const y = scaleLinear().domain([0, 0.8]).range([plotH - m.b + 10, m.t])
  const maxN = Math.max(...model.map((d) => d.n))
  const pathOf = (pts: CalPoint[]) => pts.map((d, i) => `${i ? 'L' : 'M'}${x(d.p)},${y(d.freq)}`).join('')
  return (
    <div ref={ref} className="w-full" style={{ height }}>
      {width > 0 && (
        <svg width={width} height={height} className="block">
          {[0, 0.2, 0.4, 0.6, 0.8].map((t) => (
            <g key={t}>
              <line x1={m.l} x2={width - m.r} y1={y(t)} y2={y(t)} stroke="var(--border)" />
              <text x={m.l - 8} y={y(t) + 4} textAnchor="end" fontSize={11} fill="var(--text-subtle)" className="num">{Math.round(t * 100)}</text>
              <text x={x(t)} y={plotH + 4} textAnchor="middle" fontSize={11} fill="var(--text-subtle)" className="num">{Math.round(t * 100)}</text>
            </g>
          ))}
          <line x1={x(0)} y1={y(0)} x2={x(0.8)} y2={y(0.8)} stroke="var(--text-subtle)" strokeDasharray="3 4" />
          <text x={x(0.62)} y={y(0.66)} fontSize={11} fill="var(--text-subtle)" transform={`rotate(${-Math.atan2(y(0) - y(0.8), x(0.8) - x(0)) * 180 / Math.PI} ${x(0.62)} ${y(0.66)})`}>
            calibración perfecta
          </text>
          <path d={pathOf(market)} fill="none" stroke="var(--text-muted)" strokeWidth={1.5} strokeDasharray="4 4" />
          {market.map((d) => (
            <circle key={`k${d.p}`} cx={x(d.p)} cy={y(d.freq)} r={3.5} fill="var(--surface-1)" stroke="var(--text-muted)" strokeWidth={1.5} />
          ))}
          {model.map((d) => (
            <line key={`e${d.p}`} x1={x(d.p)} x2={x(d.p)} y1={y(d.lo)} y2={y(d.hi)} stroke="var(--accent)" strokeOpacity={0.5} strokeWidth={1.5} />
          ))}
          <motion.path d={pathOf(model)} fill="none" stroke="var(--accent)" strokeWidth={2} initial={{ pathLength: 0 }} animate={{ pathLength: 1 }} transition={{ duration: 0.8 }} />
          {model.map((d) => (
            <circle key={`m${d.p}`} cx={x(d.p)} cy={y(d.freq)} r={3.5} fill="var(--accent)" />
          ))}
          <text x={width - m.r} y={plotH + 20} textAnchor="end" fontSize={11} fill="var(--text-muted)">Probabilidad predicha (%) →</text>
          <text x={m.l} y={m.t - 2} fontSize={11} fill="var(--text-muted)" dx={4}>↑ Frecuencia observada (%)</text>
          {model.map((d) => {
            const h = (d.n / maxN) * (histH - 8)
            return <rect key={`h${d.p}`} x={x(d.p) - 7} width={14} y={height - h} height={h} rx={2} fill="var(--border-strong)" />
          })}
        </svg>
      )}
    </div>
  )
}

/* ---------------------------------------------------------------- carrera de xG */

type RaceShot = { side: 'home' | 'away'; minute: number; xg: number; outcome: string; player: string }

/** xG acumulado de cada equipo a lo largo del partido; los goles, marcados sobre la línea. */
export function XgRace({ shots, homeName, awayName, height = 240 }: { shots: RaceShot[]; homeName: string; awayName: string; height?: number }) {
  const [ref, width] = useWidth<HTMLDivElement>()
  const [hover, setHover] = useState<number | null>(null)
  const m = { t: 16, r: 96, b: 26, l: 36 }
  const end = Math.max(95, ...shots.map((s) => s.minute + 2))
  const steps = (side: 'home' | 'away') => {
    const ss = shots.filter((s) => s.side === side).sort((a, b) => a.minute - b.minute)
    let acc = 0
    const pts: { minute: number; xg: number; shot?: RaceShot }[] = [{ minute: 0, xg: 0 }]
    ss.forEach((s) => {
      pts.push({ minute: s.minute, xg: acc })
      acc += s.xg
      pts.push({ minute: s.minute, xg: acc, shot: s })
    })
    pts.push({ minute: end, xg: acc })
    return pts
  }
  const home = steps('home')
  const away = steps('away')
  const max = Math.max(0.5, home.at(-1)!.xg, away.at(-1)!.xg)
  const x = scaleLinear().domain([0, end]).range([m.l, Math.max(m.l + 1, width - m.r)])
  const y = scaleLinear().domain([0, max * 1.1]).nice(4).range([height - m.b, m.t])
  const path = (pts: { minute: number; xg: number }[]) => pts.map((p, i) => `${i ? 'L' : 'M'}${x(p.minute)},${y(p.xg)}`).join('')
  // Etiquetas finales separadas al menos 30px para que no se solapen
  let yHome = y(home.at(-1)!.xg)
  let yAway = y(away.at(-1)!.xg)
  if (Math.abs(yHome - yAway) < 30) {
    const mid = (yHome + yAway) / 2
    const up = yHome <= yAway
    yHome = mid + (up ? -15 : 15)
    yAway = mid + (up ? 15 : -15)
  }
  const labelY = { home: yHome, away: yAway }
  const at = (pts: { minute: number; xg: number }[], minute: number) => pts.filter((p) => p.minute <= minute).at(-1)?.xg ?? 0
  return (
    <div ref={ref} className="relative w-full" style={{ height }}>
      {width > 0 && (
        <svg
          width={width}
          height={height}
          className="block"
          onMouseMove={(e) => setHover(Math.max(0, Math.min(end, Math.round(x.invert(e.clientX - e.currentTarget.getBoundingClientRect().left)))))}
          onMouseLeave={() => setHover(null)}
        >
          {y.ticks(4).map((t) => (
            <g key={t}>
              <line x1={m.l} x2={width - m.r} y1={y(t)} y2={y(t)} stroke="var(--border)" />
              <text x={m.l - 8} y={y(t) + 4} textAnchor="end" fontSize={11} fill="var(--text-subtle)" className="num">{num(t, 1)}</text>
            </g>
          ))}
          {[0, 15, 30, 45, 60, 75, 90].map((t) => (
            <text key={t} x={x(t)} y={height - 6} textAnchor="middle" fontSize={11} fill="var(--text-subtle)" className="num">{t}′</text>
          ))}
          <line x1={x(45)} x2={x(45)} y1={m.t} y2={height - m.b} stroke="var(--border-strong)" strokeDasharray="3 4" />
          {([['home', home, 'var(--home)', homeName], ['away', away, 'var(--away)', awayName]] as const).map(([k, pts, c, name]) => (
            <g key={k}>
              <motion.path d={path(pts)} fill="none" stroke={c} strokeWidth={2} initial={{ pathLength: 0 }} animate={{ pathLength: 1 }} transition={{ duration: 0.9, ease: [0.16, 1, 0.3, 1] }} />
              {pts.filter((p) => p.shot?.outcome === 'goal').map((p, i) => (
                <circle key={i} cx={x(p.minute)} cy={y(p.xg)} r={5} fill={c} stroke="var(--surface-1)" strokeWidth={2} />
              ))}
              <text x={width - m.r + 8} y={labelY[k] - 1} fontSize={12} fill={c} className="num">
                {num(pts.at(-1)!.xg)}
              </text>
              <text x={width - m.r + 8} y={labelY[k] + 12} fontSize={11} fill="var(--text-subtle)">
                {name.length > 12 ? name.slice(0, 11) + '…' : name}
              </text>
            </g>
          ))}
          {hover !== null && <line x1={x(hover)} x2={x(hover)} y1={m.t} y2={height - m.b} stroke="var(--border-strong)" />}
        </svg>
      )}
      {hover !== null && width > 0 && (
        <div className="pointer-events-none absolute top-0 rounded-ctl border border-line-strong bg-surface-2 px-2.5 py-1.5 text-caption float-shadow" style={{ left: Math.min(x(hover) + 10, width - 150) }}>
          <div className="num text-subtle">Minuto {hover}′</div>
          <div className="num"><span className="text-home">{num(at(home, hover))}</span> · <span className="text-away">{num(at(away, hover))}</span> xG</div>
        </div>
      )}
    </div>
  )
}
