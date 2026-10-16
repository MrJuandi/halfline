import { AnimatePresence, motion } from 'motion/react'
import type { ReactNode } from 'react'
import type { MatchDetail, Markets } from '../lib/api'
import { teamName as tn } from '../lib/api'
import { num, pct, pp } from '../lib/format'
import { Momentum, ShotMap } from './pitch'
import { cx, ProbBar, TeamBadge } from './ui'

/* Fragmentos de la interfaz para la portada. Cada uno lleva data-ui: dentro valen las convenciones
   del producto (bordes de 1 px, radios pequeños, cifras en mono). Todo sale de datos reales. */

export const ease = [0.16, 1, 0.3, 1] as const
const KEYS = ['home', 'draw', 'away'] as const
const COLOR = { home: 'var(--home)', draw: 'var(--draw)', away: 'var(--away)' }

/** Cuotas medias pre-cierre y su probabilidad implícita (1 / cuota, con margen). Si la API no trae
    las cuotas, se aproximan repartiendo el margen en proporción a las probabilidades sin margen. */
export function oddsOf(market: MatchDetail['pre_match']['market']) {
  const overround = market.overround ?? 0
  const implied = KEYS.map((k) => (market.odds ? 1 / market.odds[k] : market.pre![k] * (1 + overround)))
  return { implied, odds: implied.map((i) => 1 / i), sum: 1 + overround }
}

const outcomeOf = (d: MatchDetail) =>
  d.match.home_goals > d.match.away_goals ? 'home' : d.match.home_goals < d.match.away_goals ? 'away' : 'draw'

const labelOf = (d: MatchDetail, k: (typeof KEYS)[number]) => (k === 'home' ? tn(d.match.home) : k === 'away' ? tn(d.match.away) : 'Empate')

/* ---------------------------------------------------------------- portada: tres chips vivos */

function Chip({ children, className, tilt }: { children: ReactNode; className?: string; tilt: number }) {
  return (
    <div
      data-ui
      className={cx('rounded-[12px] bg-surface-2 p-4 text-[14px] leading-[20px] transition-transform duration-300 ease-[var(--ease-out)] hover:rotate-0', className)}
      style={{ rotate: `${tilt}deg` }}
    >
      {children}
    </div>
  )
}

export function OddsChip({ d, stripped, onNext, tilt = -3, className }: { d: MatchDetail; stripped: boolean; onNext: () => void; tilt?: number; className?: string }) {
  const fair = d.pre_match.market.pre!
  const { implied, odds, sum } = oddsOf(d.pre_match.market)
  return (
    <Chip tilt={tilt} className={className}>
      <div className="flex items-center justify-between gap-3 text-muted">
        <span className="flex min-w-0 items-center gap-1.5 truncate">
          <TeamBadge team={d.match.home} size={14} />
          <span className="truncate">{tn(d.match.home)} – {tn(d.match.away)}</span>
          <TeamBadge team={d.match.away} size={14} />
        </span>
        <button onClick={onNext} className="shrink-0 rounded-[6px] bg-surface-3 px-2 py-0.5 text-fg transition-colors hover:bg-surface-3 hover:text-fg active:scale-95">
          Otro
        </button>
      </div>
      <div className="mt-2.5 grid grid-cols-3 gap-1.5">
        {KEYS.map((k, i) => (
          <div key={k} className="rounded-[6px] bg-surface-3 px-2 py-1.5">
            <div className="text-[13px] text-muted">{k === 'home' ? '1' : k === 'draw' ? 'X' : '2'}</div>
            <AnimatePresence mode="popLayout" initial={false}>
              <motion.div
                key={`${stripped}-${d.match.match_id}`}
                initial={{ y: 10, opacity: 0 }}
                animate={{ y: 0, opacity: 1 }}
                exit={{ y: -10, opacity: 0 }}
                transition={{ duration: 0.35, ease, delay: i * 0.05 }}
                className="tnum text-[20px] font-semibold tracking-[-0.01em]"
                style={{ color: COLOR[k] }}
              >
                {stripped ? pct(fair[k], 1) : num(odds[i])}
              </motion.div>
            </AnimatePresence>
          </div>
        ))}
      </div>
      <div className="mt-2.5 flex items-center justify-between text-muted">
        <span>{stripped ? 'Probabilidad real' : 'Cuota media de las casas'}</span>
        <span className={cx('tnum font-medium transition-colors', stripped ? 'text-pos' : 'text-neg')}>
          suma {pct(stripped ? 1 : sum, 1)}
        </span>
      </div>
      <span className="sr-only">{implied.map((v) => pct(v, 1)).join(', ')}</span>
    </Chip>
  )
}

/** Barra 1X2 que sobresale del 100 % mientras el margen sigue dentro. */
export function MarginBar({ d, stripped, tilt = 2, className }: { d: MatchDetail; stripped: boolean; tilt?: number; className?: string }) {
  const fair = d.pre_match.market.pre!
  const o = d.pre_match.market.overround ?? 0
  const { implied } = oddsOf(d.pre_match.market)
  const scale = stripped ? 1 : 1 + o
  return (
    <Chip tilt={tilt} className={className}>
      <div className="flex justify-between text-muted">
        <span>Local · empate · visitante</span>
        <span className="tnum">{stripped ? 'margen 0,0 %' : `margen ${pct(o, 1)}`}</span>
      </div>
      <div className="relative mt-3 h-3">
        <motion.div className="absolute inset-y-0 left-0 flex gap-[2px]" initial={false} animate={{ width: `${(scale / (1 + o)) * 100}%` }} transition={{ duration: 0.9, ease }}>
          {KEYS.map((k, i) => (
            <motion.div key={k} className="h-full first:rounded-l-[3px] last:rounded-r-[3px]" initial={false} animate={{ flexGrow: stripped ? fair[k] : implied[i] }} transition={{ duration: 0.9, ease }} style={{ flexBasis: 0, background: COLOR[k] }} />
          ))}
        </motion.div>
        <div className="absolute -inset-y-1.5 w-[2px] rounded-full bg-fg" style={{ left: `${(1 / (1 + o)) * 100}%` }} title="100 %" />
      </div>
      <div className="mt-2 flex justify-between text-muted">
        <span>0 %</span>
        <span style={{ marginRight: `${(o / (1 + o)) * 100}%` }}>100 %</span>
      </div>
    </Chip>
  )
}

export function MarginSwitch({ on, onChange, tilt = -2, className }: { on: boolean; onChange: (v: boolean) => void; tilt?: number; className?: string }) {
  return (
    <Chip tilt={tilt} className={cx('flex items-center gap-4', className)}>
      <div className="min-w-0 flex-1">
        <div className="font-medium text-fg">Quitar el margen</div>
        <div className="text-muted">{on ? 'Lo que queda es la probabilidad' : 'Lo que cobra la casa sigue dentro'}</div>
      </div>
      <button
        role="switch"
        aria-checked={on}
        aria-label="Quitar el margen de las cuotas"
        onClick={() => onChange(!on)}
        className={cx('relative h-7 w-12 shrink-0 rounded-full transition-colors duration-200', on ? 'bg-accent' : 'bg-surface-3')}
      >
        <motion.span className="absolute top-1 left-1 size-5 rounded-full bg-fg" animate={{ x: on ? 20 : 0 }} transition={{ type: 'spring', stiffness: 500, damping: 32 }} />
      </button>
    </Chip>
  )
}

/* ---------------------------------------------------------------- cómo funciona: cuatro etapas */

export const STAGES = [
  { name: 'Cuotas', clause: ['Primero, lo que', 'paga la casa.'] },
  { name: 'Sin margen', clause: ['Después, lo que', 'queda sin margen.'] },
  { name: 'Modelo', clause: ['Luego, lo que', 'dice el modelo.'] },
  { name: 'Resultado', clause: ['Y al final, lo', 'que pasó.'] },
]

export function StageFragment({ d, stage }: { d: MatchDetail; stage: number }) {
  const fair = d.pre_match.market.pre!
  const o = d.pre_match.market.overround ?? 0
  const { implied, odds } = oddsOf(d.pre_match.market)
  const model = d.pre_match.model?.probs
  const out = outcomeOf(d)
  return (
    <div data-ui className="w-full max-w-[520px] rounded-[14px] bg-surface-1 p-6 text-[15px] leading-[22px] md:p-7">
      <div className="mb-5 flex items-center gap-2 text-[16px] font-medium">
        <TeamBadge team={d.match.home} size={18} />
        {tn(d.match.home)}
        <span className="text-subtle">–</span>
        {tn(d.match.away)}
        <TeamBadge team={d.match.away} size={18} />
      </div>
      <AnimatePresence mode="wait" initial={false}>
        <motion.div key={stage} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -6 }} transition={{ duration: 0.2, ease }}>
          {stage === 0 && (
            <div className="space-y-2">
              {KEYS.map((k, i) => (
                <div key={k} className="grid grid-cols-[1fr_72px_72px] items-center gap-3 rounded-[8px] bg-surface-2 px-4 py-3">
                  <span className="truncate">{labelOf(d, k)}</span>
                  <span className="tnum text-right text-[18px] font-semibold">{num(odds[i])}</span>
                  <span className="tnum text-right text-muted">{pct(implied[i], 1)}</span>
                </div>
              ))}
              <div className="flex justify-between px-3 pt-2 text-muted">
                <span>1 / cuota, sumado</span>
                <span className="tnum font-medium text-neg">{pct(1 + o, 1)}</span>
              </div>
            </div>
          )}
          {stage === 1 && (
            <div>
              <ProbBar probs={fair} height={28} labels />
              <div className="mt-3 grid grid-cols-3 gap-2 text-muted">
                {KEYS.map((k) => (
                  <span key={k} className="truncate">{labelOf(d, k)}</span>
                ))}
              </div>
              <p className="mt-4 rounded-[6px] bg-surface-2 px-3 py-2.5 text-muted">
                El {pct(o, 1)} que sobraba era la comisión. Se quita más a la sorpresa que al favorito, porque es donde las casas cargan más margen.
              </p>
            </div>
          )}
          {stage === 2 && (
            <div className="space-y-4">
              {KEYS.map((k) => (
                <div key={k} className="grid grid-cols-[110px_1fr_64px] items-center gap-3">
                  <span className="truncate">{labelOf(d, k)}</span>
                  <div className="relative h-5">
                    <div className="absolute inset-x-0 top-1/2 h-px bg-line-strong" />
                    <div className="absolute top-1/2 size-3.5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-subtle bg-surface-1" style={{ left: `${fair[k] * 100}%` }} />
                    {model && (
                      <motion.div
                        className="absolute top-1/2 size-3.5 -translate-x-1/2 -translate-y-1/2 rounded-full"
                        style={{ background: COLOR[k] }}
                        initial={{ left: `${fair[k] * 100}%` }}
                        animate={{ left: `${model[k] * 100}%` }}
                        transition={{ duration: 0.8, delay: 0.1, ease }}
                      />
                    )}
                  </div>
                  <span className="tnum text-right text-muted">{model ? pp(model[k] - fair[k]) : '–'}</span>
                </div>
              ))}
              <div className="flex gap-4 pt-1 text-subtle">
                <span className="flex items-center gap-1.5"><span className="size-2.5 rounded-full bg-fg" /> {d.pre_match.model?.name ?? 'Modelo'}</span>
                <span className="flex items-center gap-1.5"><span className="size-2.5 rounded-full border-2 border-subtle" /> Mercado</span>
              </div>
            </div>
          )}
          {stage === 3 && (
            <div>
              <div className="tnum mb-4 text-center text-[56px] leading-none font-semibold tracking-[-0.03em]">
                {d.match.home_goals}–{d.match.away_goals}
              </div>
              <div className="space-y-2">
                {[
                  { who: 'Mercado', p: fair[out] },
                  ...(model ? [{ who: d.pre_match.model!.name, p: model[out] }] : []),
                ].map((r) => (
                  <div key={r.who} className="flex items-center justify-between rounded-[6px] bg-surface-2 px-3 py-2.5">
                    <span>{r.who} daba a «{labelOf(d, out)}»</span>
                    <span className="tnum font-medium">{pct(r.p)}</span>
                  </div>
                ))}
              </div>
              <p className="mt-3 text-muted">Un partido no demuestra nada. Miles de partidos, sí: por eso se mide con log-loss sobre toda la temporada.</p>
            </div>
          )}
        </motion.div>
      </AnimatePresence>
    </div>
  )
}

/* ---------------------------------------------------------------- casas frente a Polymarket */

export function MarginHistogram({ m }: { m: Markets }) {
  const W = 640
  const H = 260
  const pad = { l: 8, r: 8, t: 36, b: 34 }
  const lo = -0.02
  const hi = 0.1
  const idx = m.edges.map((e, i) => ({ e, i })).filter(({ e }) => e >= lo - 1e-9 && e < hi - 1e-9)
  const bw = (W - pad.l - pad.r) / idx.length
  const max = Math.max(...m.books.hist, ...m.polymarket.hist)
  const x = (v: number) => pad.l + ((v - lo) / (hi - lo)) * (W - pad.l - pad.r)
  const h = (c: number) => (c / max) * (H - pad.t - pad.b)
  const series = [
    { key: 'polymarket', hist: m.polymarket.hist, color: 'var(--accent)', mean: m.polymarket.mean, label: 'Polymarket' },
    { key: 'books', hist: m.books.hist, color: 'var(--away)', mean: m.books.mean, label: 'Casas' },
  ]
  return (
    <figure data-ui className="w-full">
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full overflow-visible" role="img" aria-label={`Suma de probabilidades en ${m.n} partidos: Polymarket ${pct(1 + m.polymarket.mean, 1)}, casas ${pct(1 + m.books.mean, 1)}`}>
        {series.map((s, si) =>
          idx.map(({ i, e }, j) => (
            <motion.rect
              key={`${s.key}-${i}`}
              x={pad.l + j * bw + 1}
              width={bw - 2}
              rx={1.5}
              fill={s.color}
              initial={{ y: H - pad.b, height: 0 }}
              whileInView={{ y: H - pad.b - h(s.hist[i]), height: h(s.hist[i]) }}
              viewport={{ once: true, amount: 0.2 }}
              transition={{ duration: 0.7, delay: si * 0.35 + Math.abs(e - s.mean) * 6, ease }}
              opacity={0.9}
            />
          )),
        )}
        <line x1={x(0)} x2={x(0)} y1={pad.t} y2={H - pad.b + 4} stroke="var(--text)" strokeWidth={1.5} />
        {series.map((s) => (
          <text key={s.key} className="hidden md:inline" x={x(s.mean) + (s.key === 'polymarket' ? 30 : 0)} y={H - pad.b - h(Math.max(...s.hist)) - 10} fill={s.color} fontSize={13} fontWeight={600} textAnchor={s.key === 'polymarket' ? 'start' : 'middle'}>
            {s.label} {pct(1 + s.mean, 1)}
          </text>
        ))}
        {[-0.02, 0, 0.04, 0.06, 0.08].map((t) => (
          <text key={t} className={t === 0 ? '' : 'hidden md:inline'} x={x(t)} y={H - 10} fill={t === 0 ? 'var(--text)' : 'var(--text-muted)'} fontWeight={t === 0 ? 600 : 400} fontSize={t === 0 ? 22 : 13} textAnchor="middle">{t === 0 ? '100 %' : pct(1 + t)}</text>
        ))}
      </svg>
      <div className="mt-5 flex flex-wrap gap-x-6 gap-y-2 text-[15px]">
        {series.map((s) => (
          <span key={s.key} className="flex items-center gap-2">
            <span className="size-3 rounded-[3px]" style={{ background: s.color }} />
            {s.label} <span className="tnum font-semibold">{pct(1 + s.mean, 1)}</span>
          </span>
        ))}
        <span className="text-muted">100 % = sin comisión</span>
      </div>
      <figcaption className="sr-only">Distribución de la suma de las tres probabilidades implícitas antes del partido.</figcaption>
    </figure>
  )
}

export function AccuracyStrip({ m }: { m: Markets }) {
  const rows = [...m.accuracy].sort((a, b) => a.logloss - b.logloss)
  const lo = 0.97
  const hi = 1.0
  const x = (v: number) => ((v - lo) / (hi - lo)) * 100
  const isMarket = (s: string) => !s.startsWith('Modelo') && !s.startsWith('Meta')
  return (
    <div data-ui className="w-full text-[14px]">
      {rows.map((r, i) => (
        <div key={r.source} className="grid grid-cols-[minmax(0,120px)_minmax(0,1fr)_48px] items-center gap-3 py-2 md:grid-cols-[minmax(0,170px)_minmax(0,1fr)_56px] md:gap-4">
          <span className={cx('truncate', isMarket(r.source) ? 'text-fg' : 'text-muted')}>{r.source}</span>
          <div className="relative h-5">
            <div className="absolute inset-x-0 top-1/2 h-[2px] rounded-full bg-surface-3" />
            <motion.div
              className="absolute top-1/2 size-3.5 -translate-x-1/2 -translate-y-1/2 rounded-full"
              style={{ background: isMarket(r.source) ? 'var(--accent)' : 'var(--text-subtle)' }}
              initial={{ left: '0%', opacity: 0 }}
              whileInView={{ left: `${x(r.logloss)}%`, opacity: 1 }}
              viewport={{ once: true }}
              transition={{ duration: 0.8, delay: 0.1 + i * 0.07, ease }}
            />
          </div>
          <span className="tnum text-right text-muted">{num(r.logloss, 3)}</span>
        </div>
      ))}
      <div className="grid grid-cols-[minmax(0,120px)_minmax(0,1fr)_48px] gap-3 pt-2 md:grid-cols-[minmax(0,170px)_minmax(0,1fr)_56px] md:gap-4 text-[13px] text-muted">
        <span />
        <span className="flex justify-between"><span>← mejor</span><span>log-loss</span></span>
        <span />
      </div>
    </div>
  )
}

/* ---------------------------------------------------------------- ficha con notas al margen */

export type NoteKey = 'score' | 'probs' | 'elo' | 'form' | 'shots' | 'momentum'

export const NOTES: { key: NoteKey; side: 'l' | 'r'; title: string; text: string }[] = [
  { key: 'score', side: 'l', title: 'Marcador y xG', text: 'Lo que pasó y lo que debió pasar, uno al lado del otro.' },
  { key: 'probs', side: 'r', title: 'Modelo y mercado', text: 'Las dos probabilidades 1X2 y la diferencia en puntos.' },
  { key: 'elo', side: 'l', title: 'Elo antes del partido', text: 'La fuerza de cada equipo con solo partidos anteriores.' },
  { key: 'form', side: 'r', title: 'Forma reciente', text: 'xG a favor y en contra en los últimos cinco partidos.' },
  { key: 'shots', side: 'l', title: 'Mapa de tiros', text: 'Cada tiro en su sitio; el tamaño es su xG.' },
  { key: 'momentum', side: 'r', title: 'Momentum', text: 'Quién dominaba cada minuto, con goles y tarjetas.' },
]

/** Alto de cada parte de la ficha: las notas se alinean con ellas. */
export const PART_TOP: Record<NoteKey, number> = { score: 20, probs: 108, elo: 232, form: 318, shots: 404, momentum: 640 }

export function MatchFile({ d, focus }: { d: MatchDetail; focus: NoteKey | null }) {
  const m = d.match
  const fair = d.pre_match.market.pre
  const model = d.pre_match.model?.probs
  const dim = (k: NoteKey) => ({ opacity: focus && focus !== k ? 0.28 : 1, transition: 'opacity 220ms var(--ease-out)' })
  const H = d.pre_match.home
  const A = d.pre_match.away
  return (
    <div data-ui className="relative w-full max-w-[400px] rounded-[12px] bg-surface-1 p-5 text-[13px] leading-[18px]" style={{ height: 800 }}>
      <div className="absolute inset-x-5" style={{ top: PART_TOP.score, ...dim('score') }}>
        <div className="flex items-center justify-between">
          <span className="flex items-center gap-2 font-medium"><TeamBadge team={m.home} size={22} />{tn(m.home)}</span>
          <span className="tnum rounded-[6px] bg-surface-3 px-2 py-1 text-[18px] font-semibold">{m.home_goals}–{m.away_goals}</span>
          <span className="flex items-center gap-2 font-medium">{tn(m.away)}<TeamBadge team={m.away} size={22} /></span>
        </div>
        <div className="tnum mt-2 text-center text-muted">{num(m.home_xg)} – {num(m.away_xg)} xG</div>
      </div>
      <div className="absolute inset-x-5" style={{ top: PART_TOP.probs, ...dim('probs') }}>
        <div className="mb-1.5 flex justify-between text-subtle"><span>Mercado sin margen</span>{fair && <span className="tnum">{pct(fair.home)} · {pct(fair.draw)} · {pct(fair.away)}</span>}</div>
        {fair && <ProbBar probs={fair} height={8} muted />}
        <div className="mt-3 mb-1.5 flex justify-between text-subtle"><span>{d.pre_match.model?.name ?? 'Modelo'}</span>{model && <span className="tnum">{pct(model.home)} · {pct(model.draw)} · {pct(model.away)}</span>}</div>
        {model && <ProbBar probs={model} height={8} />}
      </div>
      <div className="absolute inset-x-5 grid grid-cols-2 gap-2" style={{ top: PART_TOP.elo, ...dim('elo') }}>
        {[H, A].map((t, i) => (
          <div key={i} className="rounded-[6px] bg-surface-2 px-3 py-2">
            <div className="text-muted">Elo {i ? 'visitante' : 'local'}</div>
            <div className="tnum text-[16px] font-medium">{t.elo ? Math.round(t.elo) : '–'}</div>
          </div>
        ))}
      </div>
      <div className="absolute inset-x-5 grid grid-cols-2 gap-2" style={{ top: PART_TOP.form, ...dim('form') }}>
        {[H, A].map((t, i) => (
          <div key={i} className="rounded-[6px] bg-surface-2 px-3 py-2">
            <div className="text-muted">xG últimos 5</div>
            <div className="tnum text-[16px] font-medium">{num(t.form.xg_for, 1)} <span className="text-muted">/ {num(t.form.xg_against, 1)}</span></div>
          </div>
        ))}
      </div>
      <div className="absolute inset-x-5" style={{ top: PART_TOP.shots, ...dim('shots') }}>
        <ShotMap shots={d.shots} homeName={tn(m.home)} awayName={tn(m.away)} active={null} onActive={() => {}} />
      </div>
      <div className="absolute inset-x-5" style={{ top: PART_TOP.momentum, ...dim('momentum') }}>
        <Momentum points={d.momentum} events={d.events} />
      </div>
    </div>
  )
}
