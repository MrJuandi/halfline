import { ArrowDown, ArrowUp } from 'lucide-react'
import { motion } from 'motion/react'
import { useMemo, useState } from 'react'
import type { Role, SeasonShot, SquadPlayer, TeamAnalysis } from '../lib/api'
import { num, pct, signed } from '../lib/format'
import { L, W } from './pitch'
import { cx, Panel, PanelHeader, Segmented } from './ui'

/* ---------------------------------------------------------------- foto de jugador */

export function PlayerPhoto({ name, photo, size = 28 }: { name: string; photo: string | null; size?: number }) {
  const [failed, setFailed] = useState(false)
  const initials = name.split(' ').filter(Boolean).slice(0, 2).map((w) => w[0]).join('').toUpperCase()
  return (
    <span className="relative inline-grid shrink-0 place-items-center overflow-hidden rounded-full bg-surface-3 hairline" style={{ width: size, height: size }}>
      {photo && !failed ? (
        <img src={photo} alt="" loading="lazy" onError={() => setFailed(true)} className="h-full w-full object-cover" />
      ) : (
        <span className="text-muted" style={{ fontSize: size * 0.36 }}>{initials}</span>
      )}
    </span>
  )
}

const ROLE_LABEL: Record<Role, string> = { POR: 'Portero', DEF: 'Defensa', MED: 'Centrocampista', DEL: 'Delantero' }
export const ROLE_ORDER: Role[] = ['POR', 'DEF', 'MED', 'DEL']

/* ---------------------------------------------------------------- plantilla */

type ColKey = 'minutes' | 'starts' | 'goals' | 'xg' | 'gmx' | 'assists' | 'xa' | 'chances' | 'dribbles' | 'tackles' | 'rating'
const COLS: { k: ColKey; label: string; title: string; digits: number; per90: boolean }[] = [
  { k: 'minutes', label: 'Min', title: 'Minutos jugados', digits: 0, per90: false },
  { k: 'starts', label: 'Tit', title: 'Partidos como titular', digits: 0, per90: false },
  { k: 'goals', label: 'G', title: 'Goles', digits: 0, per90: true },
  { k: 'xg', label: 'xG', title: 'Goles esperados', digits: 1, per90: true },
  { k: 'gmx', label: 'G−xG', title: 'Goles menos goles esperados: positivo = finaliza por encima de lo esperado', digits: 1, per90: false },
  { k: 'assists', label: 'A', title: 'Asistencias', digits: 0, per90: true },
  { k: 'xa', label: 'xA', title: 'Asistencias esperadas', digits: 1, per90: true },
  { k: 'chances', label: 'Ocas.', title: 'Ocasiones creadas', digits: 0, per90: true },
  { k: 'dribbles', label: 'Reg.', title: 'Regates completados', digits: 0, per90: true },
  { k: 'tackles', label: 'Ent.', title: 'Entradas', digits: 0, per90: true },
  { k: 'rating', label: 'Nota', title: 'Nota media ponderada por minutos', digits: 2, per90: false },
]

function value(p: SquadPlayer, k: ColKey, per90: boolean): number | null {
  if (k === 'rating') return p.rating
  if (k === 'starts') return p.starts
  if (k === 'minutes') return p.minutes
  if (k === 'gmx') return (p.goals ?? 0) - (p.xg ?? 0)
  const v = (p[k] as number | undefined) ?? 0
  return per90 ? (p.minutes ? (v / p.minutes) * 90 : null) : v
}

export function SquadTable({ squad, onSelect, selected }: { squad: SquadPlayer[]; onSelect: (id: string) => void; selected: string | null }) {
  const [sort, setSort] = useState<{ k: ColKey; dir: 1 | -1 }>({ k: 'minutes', dir: -1 })
  const [per90, setPer90] = useState(false)
  const [role, setRole] = useState<'all' | Role>('all')
  const rows = useMemo(() => {
    const r = squad.filter((p) => role === 'all' || p.role === role)
    return r.sort((a, b) => ((value(a, sort.k, per90) ?? -1e9) - (value(b, sort.k, per90) ?? -1e9)) * sort.dir)
  }, [squad, sort, per90, role])
  const max = useMemo(() => Object.fromEntries(COLS.map((c) => [c.k, Math.max(...squad.map((p) => Math.abs(value(p, c.k, per90) ?? 0)))])), [squad, per90])
  return (
    <Panel className="overflow-hidden">
      <PanelHeader
        title="Plantilla"
        sub={`${squad.length} jugadores con minutos · ${per90 ? 'valores por 90 minutos' : 'totales de la temporada'}`}
        aside={
          <>
            <Segmented id="role" value={role} onChange={setRole} options={[{ value: 'all', label: 'Todos' }, ...ROLE_ORDER.map((r) => ({ value: r, label: r }))]} />
            <Segmented id="per90" value={per90 ? 'p90' : 'tot'} onChange={(v) => setPer90(v === 'p90')} options={[{ value: 'tot', label: 'Total' }, { value: 'p90', label: '/90' }]} />
          </>
        }
      />
      <div className="overflow-x-auto">
        <table className="w-full min-w-[900px] text-label">
          <thead className="border-b border-line text-caption text-subtle">
            <tr>
              <th className="px-4 py-2 text-left font-normal">Jugador</th>
              {COLS.map((c) => (
                <th key={c.k} className="px-2 py-2 text-right font-normal" title={c.title}>
                  <button
                    onClick={() => setSort((s) => ({ k: c.k, dir: s.k === c.k ? (-s.dir as 1 | -1) : -1 }))}
                    className={cx('inline-flex items-center gap-1 hover:text-fg', sort.k === c.k && 'text-fg')}
                  >
                    {c.label}
                    {sort.k === c.k && (sort.dir === 1 ? <ArrowUp size={11} /> : <ArrowDown size={11} />)}
                  </button>
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {rows.map((p) => (
              <tr
                key={p.id}
                onClick={() => onSelect(p.id)}
                className={cx('h-11 transition-colors hover:bg-surface-2', selected === p.id && 'bg-surface-2')}
              >
                <td className="px-4">
                  <span className="flex items-center gap-2.5">
                    <PlayerPhoto name={p.name} photo={p.photo} size={26} />
                    <span className="min-w-0">
                      <span className="block truncate font-medium">{p.name}</span>
                      <span className="text-micro text-subtle">{p.role ? ROLE_LABEL[p.role] : '–'}{p.number ? ` · ${p.number}` : ''}</span>
                    </span>
                  </span>
                </td>
                {COLS.map((c) => {
                  const v = value(p, c.k, per90 && c.per90)
                  const strong = v !== null && max[c.k] > 0 && Math.abs(v) / max[c.k] > 0.66 && c.k !== 'minutes' && c.k !== 'starts'
                  return (
                    <td
                      key={c.k}
                      className={cx(
                        'num px-2 text-right',
                        c.k === 'gmx' && v !== null ? (v >= 1.5 ? 'text-pos' : v <= -1.5 ? 'text-neg' : 'text-muted') : strong ? 'font-semibold text-fg' : 'text-muted',
                      )}
                    >
                      {v === null ? '–' : c.k === 'gmx' ? signed(v, 1) : num(v, per90 && c.per90 && c.digits === 0 ? 2 : c.digits)}
                    </td>
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Panel>
  )
}

/* ---------------------------------------------------------------- goles frente a xG */

export function Finishing({ squad }: { squad: SquadPlayer[] }) {
  const pts = squad.filter((p) => (p.xg ?? 0) >= 0.8 || (p.goals ?? 0) >= 2)
  const [hover, setHover] = useState<string | null>(null)
  const max = Math.max(4, ...pts.map((p) => Math.max(p.xg ?? 0, p.goals ?? 0))) * 1.08
  const S = 320
  const m = 32
  const sc = (v: number) => m + (v / max) * (S - m * 1.6)
  const yc = (v: number) => S - m - (v / max) * (S - m * 1.6)
  const ticks = Array.from({ length: 5 }, (_, i) => Math.round((max / 4) * i))
  return (
    <Panel>
      <PanelHeader title="Goles frente a xG" sub="Encima de la diagonal: marca más de lo que dicen sus ocasiones" />
      <div className="p-4">
        <svg viewBox={`0 0 ${S} ${S}`} className="mx-auto block w-full max-w-[420px]">
          {ticks.map((t) => (
            <g key={t}>
              <line x1={m} x2={S - m * 0.6} y1={yc(t)} y2={yc(t)} stroke="var(--border)" />
              <text x={m - 6} y={yc(t) + 3} fontSize={9} textAnchor="end" fill="var(--text-subtle)" className="num">{t}</text>
              <text x={sc(t)} y={S - m + 14} fontSize={9} textAnchor="middle" fill="var(--text-subtle)" className="num">{t}</text>
            </g>
          ))}
          <line x1={sc(0)} y1={yc(0)} x2={sc(max)} y2={yc(max)} stroke="var(--text-subtle)" strokeDasharray="3 4" />
          <text x={S - m * 0.6} y={S - 6} fontSize={9} textAnchor="end" fill="var(--text-muted)">xG →</text>
          <text x={m} y={12} fontSize={9} fill="var(--text-muted)">↑ goles</text>
          {pts.map((p, i) => {
            const d = (p.goals ?? 0) - (p.xg ?? 0)
            const active = hover === p.id
            return (
              <motion.g
                key={p.id}
                initial={{ opacity: 0 }}
                animate={{ opacity: hover && !active ? 0.3 : 1 }}
                transition={{ duration: 0.3, delay: hover ? 0 : i * 0.02 }}
                onMouseEnter={() => setHover(p.id)}
                onMouseLeave={() => setHover(null)}
              >
                <circle cx={sc(p.xg ?? 0)} cy={yc(p.goals ?? 0)} r={active ? 5 : 4} fill={d >= 0 ? 'var(--pos)' : 'var(--neg)'} fillOpacity={0.85} />
                {(active || Math.abs(d) >= 2 || (p.goals ?? 0) >= max * 0.45) && (
                  <text x={sc(p.xg ?? 0) + 7} y={yc(p.goals ?? 0) + 3} fontSize={9} fill={active ? 'var(--text)' : 'var(--text-muted)'}>
                    {p.name.split(' ').slice(-1)[0]}{active && ` · ${num(p.goals ?? 0, 0)} G · ${num(p.xg ?? 0, 1)} xG`}
                  </text>
                )}
              </motion.g>
            )
          })}
        </svg>
      </div>
    </Panel>
  )
}

/* ---------------------------------------------------------------- once tipo */

export function TypicalXI({ a, onSelect }: { a: TeamAnalysis; onSelect: (id: string) => void }) {
  // Media parte vertical: portería propia abajo, ataque hacia arriba.
  const WIDTH = 68
  const HEIGHT = 80
  return (
    <div className="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1fr)_340px]">
      <Panel>
        <PanelHeader title={`Once tipo · ${a.typical_formation ?? ''}`} sub="Jugador que más veces ocupó cada puesto de la formación más usada" />
        <div className="p-4">
          <svg viewBox={`-3 -3 ${WIDTH + 6} ${HEIGHT + 6}`} className="mx-auto block w-full" style={{ maxHeight: 620 }}>
            <rect x={0} y={0} width={WIDTH} height={HEIGHT} fill="none" stroke="var(--pitch-line)" strokeWidth={0.3} />
            <line x1={0} x2={WIDTH} y1={HEIGHT / 2} y2={HEIGHT / 2} stroke="var(--pitch-line)" strokeWidth={0.3} />
            <circle cx={WIDTH / 2} cy={HEIGHT / 2} r={7} fill="none" stroke="var(--pitch-line)" strokeWidth={0.3} />
            <rect x={WIDTH / 2 - 16} y={HEIGHT - 13} width={32} height={13} fill="none" stroke="var(--pitch-line)" strokeWidth={0.3} />
            <rect x={WIDTH / 2 - 16} y={0} width={32} height={13} fill="none" stroke="var(--pitch-line)" strokeWidth={0.3} />
            {a.typical_xi.map((p, i) => {
              const cx_ = p.y * WIDTH
              const cy = HEIGHT - 4 - p.x * (HEIGHT - 10)
              const id = `xi-${i}`
              return (
                <motion.g
                  key={p.id}
                  initial={{ opacity: 0, y: 3 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.4, delay: i * 0.04, ease: [0.16, 1, 0.3, 1] }}
                  onClick={() => onSelect(p.id)}
                  className="cursor-pointer"
                >
                  <defs>
                    <clipPath id={id}><circle cx={cx_} cy={cy} r={3.6} /></clipPath>
                  </defs>
                  <circle cx={cx_} cy={cy} r={3.9} fill="var(--surface-3)" stroke="var(--accent)" strokeWidth={0.35} />
                  {p.photo && <image href={p.photo} x={cx_ - 3.6} y={cy - 3.6} width={7.2} height={7.2} clipPath={`url(#${id})`} preserveAspectRatio="xMidYMid slice" />}
                  <text x={cx_} y={cy + 6.4} fontSize={2.1} textAnchor="middle" fill="var(--text)" fontWeight={500}>{p.name.split(' ').slice(-1)[0]}</text>
                  <text x={cx_} y={cy + 8.9} fontSize={1.7} textAnchor="middle" fill="var(--text-subtle)" className="num">{p.slot_starts} de {a.formations[0]?.matches ?? '–'}</text>
                </motion.g>
              )
            })}
          </svg>
        </div>
      </Panel>
      <Panel className="self-start">
        <PanelHeader title="Formaciones" sub="Partidos y puntos por partido" />
        <ul className="divide-y divide-line">
          {a.formations.map((f) => (
            <li key={f.formation} className="px-4 py-3">
              <div className="flex items-baseline justify-between">
                <span className="num text-label font-medium">{f.formation}</span>
                <span className="num text-caption text-muted">{num(f.ppg)} pts/p</span>
              </div>
              <div className="mt-2 flex h-1.5 gap-[2px] overflow-hidden rounded-full">
                <div className="bg-accent" style={{ flex: f.w }} />
                <div className="bg-draw" style={{ flex: f.d }} />
                <div className="bg-neg" style={{ flex: f.l }} />
              </div>
              <div className="num mt-1 text-micro text-subtle">{f.matches} partidos · {f.w}V {f.d}E {f.l}D</div>
            </li>
          ))}
        </ul>
      </Panel>
    </div>
  )
}

/* ---------------------------------------------------------------- impacto */

export function ImpactChart({ a, onSelect }: { a: TeamAnalysis; onSelect: (id: string) => void }) {
  const rows = a.squad.filter((p) => p.impact).sort((x, y) => y.impact!.delta - x.impact!.delta)
  const max = Math.max(0.5, ...rows.map((p) => Math.abs(p.impact!.delta)))
  return (
    <Panel>
      <PanelHeader
        title="Impacto con y sin el jugador"
        sub={`Diferencia de xG por 90 min del equipo (a favor − en contra) con él en el campo frente a sin él · mínimo ${a.impact_min_minutes} min con y sin`}
      />
      <div className="grid grid-cols-[minmax(150px,220px)_minmax(0,1fr)_92px_92px] items-center gap-x-4 border-b border-line px-4 py-2 text-caption text-subtle">
        <span>Jugador</span>
        <span className="text-center">Peor sin él ← → Mejor con él</span>
        <span className="text-right">xGD/90 con</span>
        <span className="text-right">xGD/90 sin</span>
      </div>
      <ul className="divide-y divide-line">
        {rows.map((p, i) => {
          const d = p.impact!.delta
          const w = (Math.abs(d) / max) * 50
          return (
            <li key={p.id}>
              <button onClick={() => onSelect(p.id)} className="grid w-full grid-cols-[minmax(150px,220px)_minmax(0,1fr)_92px_92px] items-center gap-x-4 px-4 py-2 text-left transition-colors hover:bg-surface-2">
                <span className="flex min-w-0 items-center gap-2">
                  <PlayerPhoto name={p.name} photo={p.photo} size={22} />
                  <span className="truncate text-label">{p.name}</span>
                </span>
                <span className="relative h-5">
                  <span className="absolute inset-y-0 left-1/2 w-px bg-line-strong" />
                  <motion.span
                    className="absolute top-1/2 h-2.5 -translate-y-1/2 rounded-[2px]"
                    style={{ background: d >= 0 ? 'var(--pos)' : 'var(--neg)', [d >= 0 ? 'left' : 'right']: '50%' }}
                    initial={{ width: 0 }}
                    animate={{ width: `${w}%` }}
                    transition={{ duration: 0.5, delay: i * 0.015, ease: [0.16, 1, 0.3, 1] }}
                  />
                  <span className="num absolute top-1/2 -translate-y-1/2 text-micro text-muted" style={d >= 0 ? { left: `calc(50% + ${w}% + 6px)` } : { right: `calc(50% + ${w}% + 6px)` }}>
                    {signed(d, 2)}
                  </span>
                </span>
                <span className="num text-right text-label">{signed(p.impact!.xgd90_on, 2)}</span>
                <span className="num text-right text-label text-muted">{signed(p.impact!.xgd90_off, 2)}</span>
              </button>
            </li>
          )
        })}
      </ul>
      <p className="border-t border-line px-4 py-3 text-caption text-subtle">
        Es una medida descriptiva: no separa el efecto del jugador del de los compañeros con los que coincide, los rivales o el marcador. Con pocos minutos sin él, el valor es poco fiable.
      </p>
    </Panel>
  )
}

/* ---------------------------------------------------------------- estilo */

export function StyleProfile({ a }: { a: TeamAnalysis }) {
  return (
    <Panel>
      <PanelHeader title="Perfil de juego" sub={`Media por partido y percentil frente a los ${a.style[0]?.teams ?? ''} equipos de la liga esta temporada`} />
      <ul className="divide-y divide-line">
        {a.style.map((s, i) => (
          <li key={s.key} className="grid grid-cols-[minmax(140px,220px)_70px_minmax(0,1fr)_64px] items-center gap-4 px-4 py-2.5">
            <span className="text-label text-muted">{s.label}</span>
            <span className="num text-right text-label">{num(s.value, s.value >= 100 ? 0 : s.value >= 10 ? 1 : 2)}</span>
            <span className="relative h-2 rounded-full bg-surface-3">
              <motion.span
                className="absolute inset-y-0 left-0 rounded-full"
                style={{ background: 'var(--accent)', opacity: 0.35 + s.pct * 0.65 }}
                initial={{ width: 0 }}
                animate={{ width: `${Math.max(2, s.pct * 100)}%` }}
                transition={{ duration: 0.55, delay: i * 0.025, ease: [0.16, 1, 0.3, 1] }}
              />
              <span className="absolute -inset-y-1 left-1/2 w-px bg-line-strong" title="Mediana de la liga" />
            </span>
            <span className="num text-right text-caption text-subtle">{s.rank}.º</span>
          </li>
        ))}
      </ul>
      <p className="border-t border-line px-4 py-3 text-caption text-subtle">
        La barra es el percentil (0 = el valor más bajo de la liga, 100 = el más alto); la línea central marca la mitad. Que un valor sea alto no siempre es bueno: más xG concedido o más faltas es peor.
      </p>
    </Panel>
  )
}

/* ---------------------------------------------------------------- tiros de la temporada */

/** Media parte en vertical: línea de gol arriba (y = 0) y medio campo abajo (y = 52,5). */
function HalfPitchLines() {
  const st = { fill: 'none', stroke: 'var(--pitch-line)', strokeWidth: 0.3 }
  const H = L / 2
  return (
    <g>
      <rect x={0} y={0} width={W} height={H} {...st} />
      <rect x={(W - 40.32) / 2} y={0} width={40.32} height={16.5} {...st} />
      <rect x={(W - 18.32) / 2} y={0} width={18.32} height={5.5} {...st} />
      <rect x={(W - 7.32) / 2} y={-1.6} width={7.32} height={1.6} {...st} />
      <circle cx={W / 2} cy={11} r={0.35} fill="var(--pitch-line)" />
      <path d={`M ${W / 2 - 7.3} 16.5 A 9.15 9.15 0 0 0 ${W / 2 + 7.3} 16.5`} {...st} />
      <path d={`M ${W / 2 - 9.15} ${H} A 9.15 9.15 0 0 1 ${W / 2 + 9.15} ${H}`} {...st} />
    </g>
  )
}

function HalfPitch({ shots, color, title }: { shots: SeasonShot[]; color: string; title: string }) {
  // Media parte vertical: portería arriba. x (0..105) -> vertical; y (0..68) -> horizontal.
  const [hover, setHover] = useState<number | null>(null)
  const Y = (x: number) => (L - x) // distancia a la línea de gol
  const H = L / 2
  const sorted = shots.map((s, i) => ({ s, i })).sort((a, b) => b.s.xg - a.s.xg)
  const tip = hover !== null ? shots[hover] : null
  const total = shots.reduce((a, s) => a + s.xg, 0)
  const goals = shots.filter((s) => s.goal).length
  return (
    <Panel>
      <PanelHeader title={title} sub={`Rellenos: goles · ${shots.length} tiros · ${num(total, 1)} xG · ${goals} goles · ${num(total / Math.max(shots.length, 1), 2)} xG por tiro`} />
      <div className="relative p-4">
        <svg viewBox={`-2 -2 ${W + 4} ${H + 4}`} className="mx-auto block w-full" style={{ maxHeight: 520 }}>
          <HalfPitchLines />
          {sorted.map(({ s, i }) => (
            <circle
              key={i}
              cx={s.y}
              cy={Y(s.x)}
              r={0.35 + Math.sqrt(s.xg) * 1.5}
              fill={color}
              fillOpacity={s.goal ? 0.9 : 0.12}
              stroke={color}
              strokeOpacity={s.goal ? 0 : 0.45}
              strokeWidth={0.18}
              opacity={hover !== null && hover !== i ? 0.2 : 1}
              onMouseEnter={() => setHover(i)}
              onMouseLeave={() => setHover(null)}
            />
          ))}
        </svg>
        {tip && (
          <div className="pointer-events-none absolute right-6 top-6 rounded-ctl border border-line-strong bg-surface-2 px-3 py-2 text-caption float-shadow">
            <div className="font-medium text-fg">{tip.player}</div>
            <div className="num text-muted">{tip.minute}′ · {num(tip.xg)} xG · {tip.goal ? 'gol' : 'sin gol'}</div>
          </div>
        )}
      </div>
    </Panel>
  )
}

export function SeasonShots({ a, team }: { a: TeamAnalysis; team: string }) {
  const max = Math.max(1, ...a.goals_by_15.for, ...a.goals_by_15.against)
  const bins = ['0–15', '15–30', '30–45', '45–60', '60–75', '75–90+']
  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
      <HalfPitch shots={a.shots.for} color="var(--accent)" title={`Tiros de ${team}`} />
      <HalfPitch shots={a.shots.against} color="var(--neg)" title="Tiros concedidos" />
      <Panel className="lg:col-span-2">
        <PanelHeader title="Goles por tramo de partido" sub="A favor arriba, en contra abajo" />
        <div className="grid grid-cols-6 gap-3 px-4 py-4">
          {bins.map((b, i) => (
            <div key={b} className="flex flex-col items-center gap-1">
              <div className="flex h-20 w-full items-end justify-center">
                <motion.div className="w-7 rounded-t-[3px] bg-accent" initial={{ height: 0 }} animate={{ height: `${(a.goals_by_15.for[i] / max) * 100}%` }} transition={{ duration: 0.5, delay: i * 0.04 }} />
              </div>
              <span className="num text-label">{a.goals_by_15.for[i]}–{a.goals_by_15.against[i]}</span>
              <div className="flex h-20 w-full items-start justify-center">
                <motion.div className="w-7 rounded-b-[3px] bg-neg/80" initial={{ height: 0 }} animate={{ height: `${(a.goals_by_15.against[i] / max) * 100}%` }} transition={{ duration: 0.5, delay: i * 0.04 }} />
              </div>
              <span className="text-micro text-subtle">{b}′</span>
            </div>
          ))}
        </div>
      </Panel>
    </div>
  )
}

/* ---------------------------------------------------------------- ficha de jugador */

export function PlayerCard({ p, onClose }: { p: SquadPlayer; onClose: () => void }) {
  const per90 = (v?: number) => (p.minutes ? ((v ?? 0) / p.minutes) * 90 : 0)
  const rows: [string, string][] = [
    ['Partidos / titular', `${p.apps} / ${p.starts}`],
    ['Minutos', num(p.minutes, 0)],
    ['Goles · xG', `${num(p.goals ?? 0, 0)} · ${num(p.xg ?? 0, 1)}`],
    ['Asist. · xA', `${num(p.assists ?? 0, 0)} · ${num(p.xa ?? 0, 1)}`],
    ['xG + xA por 90', num(per90(p.xg) + per90(p.xa), 2)],
    ['Tiros por 90', num(per90(p.shots), 2)],
    ['Ocasiones creadas por 90', num(per90(p.chances), 2)],
    ['Toques en el área por 90', num(per90(p.box_touches), 2)],
    ['Duelos ganados', p.duels_won !== undefined ? pct((p.duels_won ?? 0) / Math.max(1, (p.duels_won ?? 0) + (p.duels_lost ?? 0))) : '–'],
    ['Recuperaciones por 90', num(per90(p.recoveries), 2)],
  ]
  if (p.role === 'POR') rows.push(['Paradas', num(p.saves ?? 0, 0)], ['Goles evitados', signed(p.goals_prevented ?? 0, 2)])
  return (
    <Panel className="self-start">
      <div className="flex items-center gap-3 border-b border-line px-4 py-4">
        <PlayerPhoto name={p.name} photo={p.photo} size={48} />
        <div className="min-w-0 flex-1">
          <div className="truncate text-h3 font-semibold">{p.name}</div>
          <div className="text-caption text-subtle">{p.role ? ROLE_LABEL[p.role] : ''}{p.number ? ` · dorsal ${p.number}` : ''} · nota {num(p.rating, 2)}</div>
        </div>
        <a href={`/jugadores?jugador=${p.id}`} className="rounded-ctl px-2 py-1 text-caption text-muted hover:bg-surface-2 hover:text-fg">Perfil</a>
        <button onClick={onClose} className="rounded-ctl px-2 py-1 text-caption text-subtle hover:bg-surface-2 hover:text-fg">Cerrar</button>
      </div>
      <dl className="divide-y divide-line">
        {rows.map(([k, v]) => (
          <div key={k} className="flex items-center justify-between px-4 py-2 text-label">
            <dt className="text-muted">{k}</dt>
            <dd className="num">{v}</dd>
          </div>
        ))}
      </dl>
      {p.impact && (
        <div className="border-t border-line px-4 py-3">
          <div className="text-caption text-subtle">Con él en el campo</div>
          <div className="num mt-1 text-label">
            xG a favor {num(p.impact.xgf90_on)} · en contra {num(p.impact.xga90_on)} <span className="text-subtle">por 90</span>
          </div>
          <div className="num text-label text-muted">
            Sin él: {num(p.impact.xgf90_off)} · {num(p.impact.xga90_off)}
          </div>
          <div className={cx('num mt-1 text-label font-medium', p.impact.delta >= 0 ? 'text-pos' : 'text-neg')}>
            Impacto {signed(p.impact.delta, 2)} xGD/90
          </div>
        </div>
      )}
    </Panel>
  )
}
