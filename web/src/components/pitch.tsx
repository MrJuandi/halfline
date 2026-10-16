import { AnimatePresence, motion } from 'motion/react'
import { useMemo, useState, type ReactNode } from 'react'
import type { Cells, LineupPlayer, MatchEvent, Shot, Side } from '../lib/api'
import { num } from '../lib/format'
import { cx } from './ui'

/* Campo de 105 × 68 m. Coordenadas de PitchAPI: los tiros atacan siempre hacia x = 105.
   En el campo completo el local ataca hacia la derecha y el visitante hacia la izquierda. */

export const L = 105
export const W = 68
const SIDE_COLOR: Record<Side, string> = { home: 'var(--home)', away: 'var(--away)' }

export function PitchLines({ stroke = 'var(--pitch-line)' }: { stroke?: string }) {
  const s = { fill: 'none', stroke, strokeWidth: 0.35, vectorEffect: 'non-scaling-stroke' as const }
  return (
    <g>
      <rect x={0} y={0} width={L} height={W} {...s} />
      <line x1={L / 2} y1={0} x2={L / 2} y2={W} {...s} />
      <circle cx={L / 2} cy={W / 2} r={9.15} {...s} />
      <circle cx={L / 2} cy={W / 2} r={0.4} fill={stroke} />
      {[0, 1].map((side) => {
        const x = (v: number) => (side === 0 ? v : L - v)
        return (
          <g key={side}>
            <rect x={Math.min(x(0), x(16.5))} y={W / 2 - 20.16} width={16.5} height={40.32} {...s} />
            <rect x={Math.min(x(0), x(5.5))} y={W / 2 - 9.16} width={5.5} height={18.32} {...s} />
            <rect x={Math.min(x(0), x(-1.6))} y={W / 2 - 3.66} width={1.6} height={7.32} {...s} />
            <circle cx={x(11)} cy={W / 2} r={0.4} fill={stroke} />
            <path
              d={side === 0
                ? `M 16.5 ${W / 2 - 7.3} A 9.15 9.15 0 0 1 16.5 ${W / 2 + 7.3}`
                : `M ${L - 16.5} ${W / 2 - 7.3} A 9.15 9.15 0 0 0 ${L - 16.5} ${W / 2 + 7.3}`}
              {...s}
            />
          </g>
        )
      })}
    </g>
  )
}

function PitchSvg({ children, className, pad = 2, maxHeight = 500 }: { children: ReactNode; className?: string; pad?: number; maxHeight?: number }) {
  return (
    <svg viewBox={`${-pad} ${-pad} ${L + pad * 2} ${W + pad * 2}`} className={cx('mx-auto block h-auto w-full', className)} style={{ maxHeight }}>
      {children}
    </svg>
  )
}

/* ---------------------------------------------------------------- mapa de tiros */

const OUTCOME_LABEL: Record<Shot['outcome'], string> = {
  goal: 'Gol', saved: 'Parado', miss: 'Fuera', post: 'Al palo', blocked: 'Bloqueado', other: 'Otro',
}
const SITUATION: Record<string, string> = {
  RegularPlay: 'Jugada', FromCorner: 'Córner', SetPiece: 'Balón parado', FastBreak: 'Contraataque',
  Penalty: 'Penalti', FreeKick: 'Falta directa', ThrowInSetPiece: 'Saque de banda', IndividualPlay: 'Jugada individual',
}
const BODY: Record<string, string> = { right_foot: 'pie derecho', left_foot: 'pie izquierdo', head: 'cabeza', other: 'otra parte' }

/** Posición de un tiro en el campo completo (visitante reflejado). */
function place(s: Shot) {
  return s.side === 'home' ? { x: s.x, y: s.y } : { x: L - s.x, y: W - s.y }
}
const radius = (xg: number) => 0.6 + Math.sqrt(Math.max(xg, 0)) * 3.6

export function ShotMap({
  shots,
  homeName,
  awayName,
  active,
  onActive,
}: {
  shots: Shot[]
  homeName: string
  awayName: string
  active: number | null
  onActive: (i: number | null) => void
}) {
  const ordered = useMemo(
    () => shots.map((s, i) => ({ s, i })).sort((a, b) => b.s.xg - a.s.xg), // los grandes debajo
    [shots],
  )
  const tip = active !== null ? shots[active] : null
  const tipPos = tip ? place(tip) : null
  return (
    <div className="relative">
      <PitchSvg>
        <PitchLines />
        <text x={1} y={-0.7} fontSize={1.7} fill="var(--text-subtle)">{homeName} →</text>
        <text x={L - 1} y={-0.7} fontSize={1.7} fill="var(--text-subtle)" textAnchor="end">← {awayName}</text>
        {ordered.map(({ s, i }) => {
          const p = place(s)
          const goal = s.outcome === 'goal'
          const isActive = active === i
          const dim = active !== null && !isActive
          return (
            <motion.circle
              key={i}
              cx={p.x}
              cy={p.y}
              initial={{ r: 0, opacity: 0 }}
              animate={{ r: radius(s.xg) * (isActive ? 1.15 : 1), opacity: dim ? 0.25 : 1 }}
              transition={{ duration: 0.4, delay: Math.min(i * 0.008, 0.3), ease: [0.16, 1, 0.3, 1] }}
              fill={goal ? SIDE_COLOR[s.side] : 'transparent'}
              fillOpacity={goal ? 0.95 : 0}
              stroke={SIDE_COLOR[s.side]}
              strokeWidth={goal ? 0 : 0.35}
              strokeOpacity={0.85}
              onMouseEnter={() => onActive(i)}
              onMouseLeave={() => onActive(null)}
              className="cursor-crosshair"
            />
          )
        })}
      </PitchSvg>
      <AnimatePresence>
        {tip && tipPos && (
          <motion.div
            key={active}
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.12 }}
            className="pointer-events-none absolute z-10 w-52 -translate-x-1/2 -translate-y-full rounded-ctl border border-line-strong bg-surface-2 px-3 py-2 float-shadow"
            style={{ left: `${((tipPos.x + 2) / (L + 4)) * 100}%`, top: `calc(${((tipPos.y + 2) / (W + 4)) * 100}% - 12px)` }}
          >
            <div className="flex items-baseline justify-between gap-2">
              <span className="truncate text-label font-medium">{tip.player}</span>
              <span className="num text-caption text-subtle">{tip.minute}′</span>
            </div>
            <div className="mt-1 flex items-baseline justify-between text-caption text-muted">
              <span>{OUTCOME_LABEL[tip.outcome]} · {BODY[tip.body] ?? tip.body}</span>
              <span className="num text-fg">{num(tip.xg)} xG</span>
            </div>
            <div className="text-caption text-subtle">{SITUATION[tip.situation] ?? tip.situation}</div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

export function ShotLegend() {
  return (
    <div className="flex flex-wrap items-center gap-x-5 gap-y-2 text-caption text-subtle">
      <span className="flex items-center gap-2">
        Tamaño = xG
        {[0.05, 0.2, 0.5].map((v) => (
          <span key={v} className="flex items-center gap-1">
            <svg width={radius(v) * 4 + 2} height={radius(v) * 4 + 2} viewBox={`0 0 ${radius(v) * 2 + 0.5} ${radius(v) * 2 + 0.5}`}>
              <circle cx={radius(v) + 0.25} cy={radius(v) + 0.25} r={radius(v)} fill="none" stroke="var(--text-subtle)" strokeWidth={0.35} />
            </svg>
            <span className="num">{num(v)}</span>
          </span>
        ))}
      </span>
      <span className="flex items-center gap-1.5">
        <span className="size-2.5 rounded-full bg-muted" /> Gol
      </span>
      <span className="flex items-center gap-1.5">
        <span className="size-2.5 rounded-full border border-muted" /> Sin gol
      </span>
    </div>
  )
}

export { OUTCOME_LABEL, SITUATION }

/* ---------------------------------------------------------------- momentum */

export function Momentum({ points, events }: { points: { minute: number; value: number }[]; events: MatchEvent[] }) {
  const [hover, setHover] = useState<number | null>(null)
  const H = 120
  const max = Math.max(1, ...points.map((p) => Math.abs(p.value)))
  const last = Math.max(90, ...points.map((p) => p.minute))
  const bw = 1000 / (last + 1)
  const x = (m: number) => m * bw
  const goals = events.filter((e) => e.type === 'goal')
  const reds = events.filter((e) => e.type === 'redcard')
  const hp = hover !== null ? points.find((p) => p.minute === hover) : null
  return (
    <div className="relative">
      <svg viewBox={`0 -20 1000 ${H * 2 + 56}`} className="block h-auto w-full" onMouseLeave={() => setHover(null)}>
        <line x1={x(45.5)} x2={x(45.5)} y1={-6} y2={H * 2 + 6} stroke="var(--border-strong)" strokeDasharray="3 4" />
        <text x={x(45.5) + 6} y={-4} fontSize={11} fill="var(--text-subtle)">Descanso</text>
        {points.map((p, i) => {
          const h = (Math.abs(p.value) / max) * (H - 4)
          const up = p.value > 0
          return (
            <motion.rect
              key={p.minute}
              x={x(p.minute) + bw * 0.12}
              width={bw * 0.76}
              rx={Math.min(2, bw * 0.3)}
              initial={{ y: H, height: 0 }}
              animate={{ y: up ? H - h : H, height: Math.max(h, 0.5) }}
              transition={{ duration: 0.45, delay: i * 0.004, ease: [0.16, 1, 0.3, 1] }}
              fill={up ? 'var(--home)' : 'var(--away)'}
              opacity={hover === null || hover === p.minute ? 0.9 : 0.35}
              onMouseEnter={() => setHover(p.minute)}
            />
          )
        })}
        <line x1={0} x2={1000} y1={H} y2={H} stroke="var(--border-strong)" />
        {goals.map((g, i) => {
          const gx = x(Math.min(g.minute, last)) + bw / 2
          const home = g.side === 'home'
          return (
            <g key={`g${i}`} transform={`translate(${gx}, ${home ? -10 : H * 2 + 10})`}>
              <circle r={6} fill={home ? 'var(--home)' : 'var(--away)'} />
              <circle r={2.2} fill="var(--surface-1)" />
            </g>
          )
        })}
        {reds.map((r, i) => (
          <rect key={`r${i}`} x={x(r.minute) + bw / 2 - 3} y={r.side === 'home' ? -14 : H * 2 + 6} width={6} height={8} rx={1} fill="var(--neg)" />
        ))}
        {[0, 15, 30, 45, 60, 75, 90].map((m) => (
          <text key={m} x={x(m)} y={H * 2 + 32} fontSize={11} fill="var(--text-subtle)" className="num" textAnchor={m === 0 ? 'start' : 'middle'}>
            {m}′
          </text>
        ))}
      </svg>
      {hp && (
        <div
          className="pointer-events-none absolute top-0 -translate-x-1/2 rounded-ctl border border-line-strong bg-surface-2 px-2.5 py-1.5 text-caption float-shadow"
          style={{ left: `${(x(hp.minute) / 1000) * 100}%` }}
        >
          <span className="num text-fg">{hp.minute}′</span>{' '}
          <span className="text-muted">{hp.value > 0 ? 'domina el local' : hp.value < 0 ? 'domina el visitante' : 'equilibrio'}</span>
        </div>
      )}
    </div>
  )
}

/* ---------------------------------------------------------------- mapa de calor */

/** Rejilla length × width (16 × 12) en el marco del equipo que actúa: ataca hacia la derecha. */
export function Heatmap({ cells, grid, color = 'var(--accent)' }: { cells: Cells; grid: { length: number; width: number }; color?: string }) {
  const cw = L / grid.length
  const ch = W / grid.width
  const max = Math.max(1, ...cells.map((c) => c[2]))
  const id = useMemo(() => `blur-${Math.random().toString(36).slice(2)}`, [])
  return (
    <PitchSvg>
      <defs>
        <filter id={id} x="-10%" y="-10%" width="120%" height="120%">
          <feGaussianBlur stdDeviation={2.2} />
        </filter>
        <clipPath id={`${id}-clip`}>
          <rect x={0} y={0} width={L} height={W} />
        </clipPath>
      </defs>
      <rect x={0} y={0} width={L} height={W} fill="var(--surface-1)" />
      <g filter={`url(#${id})`} clipPath={`url(#${id}-clip)`}>
        {cells.map(([cx_, cy, n], i) => (
          <motion.rect
            key={`${cx_}-${cy}`}
            x={cx_ * cw}
            y={cy * ch}
            width={cw + 0.2}
            height={ch + 0.2}
            fill={color}
            initial={{ opacity: 0 }}
            animate={{ opacity: Math.pow(n / max, 0.75) * 0.95 }}
            transition={{ duration: 0.5, delay: i * 0.002 }}
          />
        ))}
      </g>
      <PitchLines stroke="color-mix(in srgb, var(--text) 22%, transparent)" />
    </PitchSvg>
  )
}

/* ---------------------------------------------------------------- alineaciones */

export function Lineups({
  home,
  away,
}: {
  home: { formation: string; starters: LineupPlayer[] }
  away: { formation: string; starters: LineupPlayer[] }
}) {
  // pitch_x: 0 = portería propia, 1 = rival; pitch_y: 0..1 a lo ancho.
  const pos = (p: LineupPlayer, side: Side) =>
    side === 'home'
      ? { x: 3 + p.x * (L / 2 - 6), y: p.y * W }
      : { x: L - 3 - p.x * (L / 2 - 6), y: W - p.y * W }
  const surname = (n: string) => {
    const parts = n.split(' ')
    return parts.length > 1 ? parts.slice(1).join(' ') : n
  }
  return (
    <PitchSvg pad={3}>
      <PitchLines />
      {(['home', 'away'] as Side[]).map((side) =>
        (side === 'home' ? home : away).starters.map((p, i) => {
          const q = pos(p, side)
          return (
            <motion.g
              key={`${side}-${i}`}
              initial={{ opacity: 0, scale: 0.6 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ duration: 0.35, delay: i * 0.025, ease: [0.16, 1, 0.3, 1] }}
              style={{ transformOrigin: `${q.x}px ${q.y}px`, transformBox: 'fill-box' }}
            >
              <circle cx={q.x} cy={q.y} r={2.1} fill={SIDE_COLOR[side]} />
              <text x={q.x} y={q.y + 0.7} fontSize={1.8} textAnchor="middle" fontWeight={600} fill="var(--bg)" className="num">
                {p.number ?? ''}
              </text>
              <text x={q.x} y={q.y + 4.4} fontSize={1.6} textAnchor="middle" fill="var(--text-muted)">
                {surname(p.name)}
                {p.captain ? ' (C)' : ''}
              </text>
            </motion.g>
          )
        }),
      )}
    </PitchSvg>
  )
}
