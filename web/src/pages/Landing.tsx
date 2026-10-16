import { ArrowLeft, ArrowRight } from 'lucide-react'
import { motion, useReducedMotion } from 'motion/react'
import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import campoFocos from '../assets/photos/campo-focos.jpg'
import estadioNoche from '../assets/photos/estadio-noche.jpg'
import { XgRace } from '../components/charts'
import {
  AccuracyStrip,
  ease,
  MarginBar,
  MarginHistogram,
  MarginSwitch,
  MatchFile,
  NOTES,
  OddsChip,
  PART_TOP,
  STAGES,
  StageFragment,
  type NoteKey,
} from '../components/landing'
import { Momentum, ShotMap } from '../components/pitch'
import { cx, FormSquares, Logo, TeamBadge } from '../components/ui'
import { api, useApi, type MatchDetail, type MatchSummary, type Markets, type Meta, type TableRow, teamName as tn } from '../lib/api'
import { int, pct, pp, seasonLabel, signed } from '../lib/format'

/* ---------------------------------------------------------------- piezas comunes */

const PAD = 'px-4 md:px-8'
const WRAP = 'mx-auto w-full max-w-[1320px]'

/** Las partes de una sección entran en orden de lectura: título, texto, figura. */
function Rise({ children, i = 0, className, y = 24 }: { children: ReactNode; i?: number; className?: string; y?: number }) {
  return (
    <motion.div
      className={className}
      initial={{ opacity: 0, y }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: '-80px' }}
      transition={{ duration: 0.7, delay: i * 0.08, ease }}
    >
      {children}
    </motion.div>
  )
}

function Button({ to, children, tone = 'solid' }: { to: string; children: ReactNode; tone?: 'solid' | 'ink' }) {
  return (
    <Link
      to={to}
      className={cx(
        'group inline-flex h-12 items-center gap-2 rounded-[8px] px-5 text-[16px] font-medium transition-[transform,background-color] duration-150 active:scale-[0.97]',
        tone === 'solid' ? 'bg-fg text-bg hover:bg-[color-mix(in_srgb,var(--text)_88%,var(--bg))]' : 'bg-bg text-fg hover:bg-surface-2',
      )}
    >
      {children}
      <ArrowRight size={17} className="transition-transform duration-200 group-hover:translate-x-0.5" />
    </Link>
  )
}

const H2 = 'text-[clamp(34px,4.4vw,64px)] leading-[1.02] font-semibold tracking-[-0.035em]'
const LEAD = 'text-[20px] leading-[1.55]'

/* ---------------------------------------------------------------- datos de la portada */

/** Partidos recientes con cuotas, xG y mapas de calor: los que se pueden enseñar enteros. */
function useShowcaseMatches() {
  const { data } = useApi<MatchSummary[]>(api.matches({ limit: 80 }))
  return useMemo(
    () => (data ?? []).filter((m) => m.market && m.has_heatmaps && m.home_xg !== null && m.home_goals + m.away_goals >= 2).slice(0, 8),
    [data],
  )
}

/* ---------------------------------------------------------------- navegación */

function TopNav() {
  return (
    <header className={cx('absolute inset-x-0 top-0 z-30', PAD)}>
      <div className={cx(WRAP, 'flex h-20 items-center gap-8')}>
        <Link to="/" className="flex items-center gap-2.5 text-[16px] font-semibold tracking-[-0.01em]">
          <Logo size={20} /> Halfline
        </Link>
        <nav className="hidden items-center gap-7 text-[16px] text-muted md:flex">
          <a href="#como" className="transition-colors hover:text-fg">Cómo funciona</a>
          <a href="#mercados" className="transition-colors hover:text-fg">Mercados</a>
          <a href="#partido" className="transition-colors hover:text-fg">El partido</a>
          <a href="#fuentes" className="transition-colors hover:text-fg">Datos</a>
        </nav>
        <Link to="/hoy" className="ml-auto inline-flex h-10 items-center gap-1.5 rounded-[8px] bg-fg px-4 text-[16px] font-medium text-bg transition-transform duration-150 active:scale-[0.97]">
          Abrir la app <ArrowRight size={15} />
        </Link>
      </div>
    </header>
  )
}

/* ---------------------------------------------------------------- portada */

function Hero({ d, onNext }: { d: MatchDetail | undefined; onNext: () => void }) {
  const { data: mk } = useApi<Markets>(api.markets)
  const [stripped, setStripped] = useState(false)
  const touched = useRef(false)
  const reduce = useReducedMotion()
  // El producto se enseña solo una vez: a los 2,6 s quita el margen, salvo que el visitante ya haya tocado
  useEffect(() => {
    if (!d || reduce) return
    const t = setTimeout(() => !touched.current && setStripped(true), 2600)
    return () => clearTimeout(t)
  }, [d, reduce])
  const toggle = (v: boolean) => {
    touched.current = true
    setStripped(v)
  }
  const line = (text: string, i: number) => (
    <span className="mask-line">
      <motion.span className="block" initial={{ y: '105%' }} animate={{ y: 0 }} transition={{ duration: 0.9, delay: 0.15 + i * 0.11, ease }}>
        {text}
      </motion.span>
    </span>
  )
  const ready = d?.pre_match.market.pre
  return (
    <section className={cx('relative flex min-h-[100svh] flex-col pt-28 pb-16 md:pt-32', PAD)}>
      <div className={cx(WRAP, 'flex flex-1 flex-col items-center justify-center')}>
        <h1 className="text-center text-[clamp(44px,10vw,150px)] leading-[0.98] font-semibold tracking-[-0.05em]">
          {line('Quita el margen.', 0)}
          {line('Mira el partido.', 1)}
        </h1>
        <motion.p
          className={cx(LEAD, 'mt-8 max-w-[40ch] text-center text-muted')}
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, delay: 0.55, ease }}
        >
          Las casas se quedan de media un {mk ? pct(mk.all_books_mean, 1) : '4,9 %'} de cada partido. Halfline lo quita y compara lo que queda con un modelo propio.
        </motion.p>
        <motion.div className="mt-8 flex flex-wrap items-center justify-center gap-4" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.7, delay: 0.65, ease }}>
          <Button to="/hoy">Ver la jornada</Button>
          <a href="#como" className="text-[16px] text-muted underline decoration-surface-3 underline-offset-4 transition-colors hover:text-fg hover:decoration-fg">
            Cómo funciona
          </a>
        </motion.div>

        {/* Tres piezas reales del producto: cuotas, barra con margen y el interruptor */}
        <motion.div
          className="mt-16 grid w-full max-w-[1200px] items-start gap-4 md:grid-cols-3 md:gap-7"
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.9, delay: 0.8, ease }}
        >
          {ready ? (
            <>
              <OddsChip d={d!} stripped={stripped} onNext={onNext} tilt={-2.5} className="md:mt-6" />
              <MarginBar d={d!} stripped={stripped} tilt={1.5} />
              <MarginSwitch on={stripped} onChange={toggle} tilt={-2} className="md:mt-10" />
            </>
          ) : (
            [0, 1, 2].map((i) => <div key={i} className="skeleton h-[150px] rounded-[12px]" />)
          )}
        </motion.div>
      </div>
    </section>
  )
}

/* ---------------------------------------------------------------- cómo funciona */

function HowItWorks({ d }: { d: MatchDetail | undefined }) {
  const [stage, setStage] = useState(0)
  const s = STAGES[stage]
  return (
    <section id="como" className="scroll-mt-0">
      <div className="grid md:min-h-[76svh] md:grid-cols-2">
        <div className={cx('order-2 flex flex-col justify-between bg-bg py-14 md:order-1 md:py-24', PAD)}>
          <Rise>
            <h2 className={cx(H2, 'max-w-[12ch]')} aria-live="polite">
              <motion.span key={stage} className="block" initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.35, ease }}>
                {s.clause[0]} {s.clause[1]}
              </motion.span>
            </h2>
          </Rise>
          <Rise i={1} className={cx(LEAD, 'mt-10 max-w-[42ch]')}>
            {stage === 0 && 'Una cuota de 2,00 parece un 50 %. Pero si sumas las tres del partido pasan del 100 %: el exceso es lo que la casa gana pase lo que pase.'}
            {stage === 1 && 'Se reparten las tres probabilidades para que sumen exactamente 100 %. Es la mejor estimación del mercado sin su comisión.'}
            {stage === 2 && 'El modelo propio solo ve partidos anteriores: Elo ajustado por xG, forma y descanso. Donde se separa del mercado, hay algo que mirar.'}
            {stage === 3 && 'Y luego se comprueba. Si el modelo dice 54 % muchas veces, el local tiene que ganar cerca del 54 % de esas veces.'}
          </Rise>
        </div>
        <div className={cx('order-1 flex items-center justify-center bg-surface-2 py-14 md:order-2 md:py-24', PAD)}>
          {d?.pre_match.market.pre ? <StageFragment d={d} stage={stage} /> : <div className="skeleton h-80 w-full max-w-[520px] rounded-[14px]" />}
        </div>
      </div>
      <div className={cx('bg-surface-1 py-8', PAD)}>
        <div className={WRAP}>
          <input
            type="range"
            min={0}
            max={3}
            step={1}
            value={stage}
            onChange={(e) => setStage(Number(e.target.value))}
            className="stage-range"
            style={{ ['--fill' as string]: `${(stage / 3) * 100}%` }}
            aria-label="Etapa"
            aria-valuetext={s.name}
          />
          <div className="mt-2 grid grid-cols-2 gap-y-2 md:grid-cols-4">
            {STAGES.map((st, i) => (
              <button
                key={st.name}
                onClick={() => setStage(i)}
                className={cx('text-left text-[16px] transition-colors md:[&:nth-child(2)]:text-center md:[&:nth-child(3)]:text-center md:[&:nth-child(4)]:text-right', i === stage ? 'font-medium text-fg' : 'text-muted hover:text-fg')}
              >
                {st.name}
              </button>
            ))}
          </div>
        </div>
      </div>
    </section>
  )
}

/* ---------------------------------------------------------------- mercados de predicción */

function PredictionMarkets() {
  const { data: m } = useApi<Markets>(api.markets)
  return (
    <section id="mercados" className={cx('scroll-mt-0 bg-bg py-28 md:py-44', PAD)}>
      <div className={cx(WRAP, 'grid gap-14 lg:grid-cols-[5fr_7fr] lg:gap-20')}>
        <div>
          <Rise>
            <h2 className={H2}>Polymarket cobra menos.</h2>
          </Rise>
          <Rise i={1} className={cx(LEAD, 'mt-8 max-w-[38ch]')}>
            {m
              ? `En los mismos ${int(m.n)} partidos, las probabilidades de las casas suman de media un ${pct(1 + m.books.mean, 1)}. Las de Polymarket, un ${pct(1 + m.polymarket.mean, 1)}: su comisión no va dentro del precio, se paga aparte al comprar.`
              : 'Las casas meten su margen dentro de la cuota. Polymarket cobra una comisión aparte al comprar, y es menor.'}
          </Rise>
          <Rise i={2} className="mt-6 max-w-[42ch] text-[16px] leading-[1.6] text-muted">
            Y aciertan lo mismo. Ningún modelo propio les gana todavía: lo decimos porque es lo que dicen los datos, y porque saberlo es el punto de partida.
          </Rise>
        </div>
        <div className="min-w-0 space-y-14">
          <Rise i={1} y={32} className="rounded-[14px] bg-surface-1 p-5 md:p-8">
            <p className="mb-6 text-[16px] font-medium">Suma de las tres probabilidades, partido a partido</p>
            {m ? <MarginHistogram m={m} /> : <div className="skeleton h-64 w-full" />}
          </Rise>
          <Rise i={2} y={32} className="rounded-[14px] bg-surface-1 p-5 md:p-8">
            <p className="mb-4 text-[16px] font-medium">Acierto antes del partido, menos es mejor</p>
            {m ? <AccuracyStrip m={m} /> : <div className="skeleton h-56 w-full" />}
          </Rise>
        </div>
      </div>
    </section>
  )
}

/* ---------------------------------------------------------------- escaparate: fila oscura, panel iluminado */

function LeagueRows() {
  const { data: meta } = useApi<Meta>(api.meta)
  const season = meta?.leagues[0]?.seasons.at(-2)
  const { data } = useApi<{ rows: TableRow[] }>(season ? api.table('E0', season) : null)
  if (!data) return <div className="skeleton h-72 w-full" />
  const rows = [...data.rows].sort((a, b) => Math.abs(b.pts - b.xpts) - Math.abs(a.pts - a.xpts)).slice(0, 7)
  const max = Math.max(...rows.map((r) => Math.abs(r.pts - r.xpts)))
  return (
    <ul className="space-y-1">
      {rows.map((r) => {
        const d = r.pts - r.xpts
        return (
          <li key={r.team} className="grid grid-cols-[minmax(0,1fr)_minmax(0,1fr)_48px] items-center gap-3 py-1.5">
            <span className="flex min-w-0 items-center gap-2">
              <TeamBadge team={r.team} size={16} />
              <span className="truncate">{tn(r.team)}</span>
              <FormSquares form={r.form.slice(-3)} size={12} />
            </span>
            <span className="relative h-2">
              <span className="absolute inset-y-[-3px] left-1/2 w-px bg-line-strong" /* taste-skill-ignore: eje del gráfico */ />
              <span className="absolute inset-y-0 rounded-[2px]" style={{ background: d >= 0 ? 'var(--pos)' : 'var(--neg)', [d >= 0 ? 'left' : 'right']: '50%', width: `${(Math.abs(d) / max) * 50}%` }} />
            </span>
            <span className={cx('tnum text-right', d >= 0 ? 'text-pos' : 'text-neg')}>{signed(d, 1)}</span>
          </li>
        )
      })}
    </ul>
  )
}

function ModelRows({ d }: { d: MatchDetail }) {
  const fair = d.pre_match.market.pre!
  const model = d.pre_match.model?.probs ?? fair
  const keys = ['home', 'draw', 'away'] as const
  return (
    <div className="space-y-4">
      {keys.map((k) => (
        <div key={k} className="grid grid-cols-[96px_1fr_52px] items-center gap-3">
          <span className="truncate">{k === 'home' ? tn(d.match.home) : k === 'away' ? tn(d.match.away) : 'Empate'}</span>
          <div className="relative h-5">
            <div className="absolute inset-x-0 top-1/2 h-px bg-line-strong" /* taste-skill-ignore: eje del gráfico */ />
            <div className="absolute top-1/2 size-3 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-subtle" style={{ left: `${fair[k] * 100}%` }} />
            <div className="absolute top-1/2 size-3 -translate-x-1/2 -translate-y-1/2 rounded-full" style={{ left: `${model[k] * 100}%`, background: `var(--${k})` }} />
          </div>
          <span className="tnum text-right text-muted">{pp(model[k] - fair[k])}</span>
        </div>
      ))}
    </div>
  )
}

function Showcase({ d }: { d: MatchDetail | undefined }) {
  const [active, setActive] = useState(0)
  const panels = useMemo(() => {
    if (!d) return []
    const home = tn(d.match.home)
    const away = tn(d.match.away)
    return [
      { name: 'Mapa de tiros', text: 'Cada tiro donde se hizo, con su xG. Los goles, rellenos.', body: <ShotMap shots={d.shots} homeName={home} awayName={away} active={null} onActive={() => {}} /> },
      { name: 'Carrera de xG', text: 'El xG acumulado minuto a minuto. Quién mereció más, y cuándo.', body: <XgRace shots={d.shots} homeName={home} awayName={away} height={200} /> },
      { name: 'Momentum', text: 'Barras arriba, domina el local; abajo, el visitante.', body: <Momentum points={d.momentum} events={d.events} /> },
      { name: 'Modelo y mercado', text: 'El punto hueco es el mercado; el relleno, el modelo.', body: <ModelRows d={d} /> },
      { name: 'Suerte en la tabla', text: 'Puntos reales menos esperados: quién está por encima de lo que merece.', body: <LeagueRows /> },
    ]
  }, [d])

  const go = (i: number) => setActive(Math.max(0, Math.min(panels.length - 1, i)))
  const p = panels[active]
  return (
    <section id="partido" className={cx('scroll-mt-0 bg-surface-1 py-28 md:py-40', PAD)}>
      <div className={cx(WRAP, 'mb-12 grid gap-6 md:grid-cols-[7fr_5fr] md:items-end')}>
        <Rise>
          <h2 className={H2}>Cada partido, entero.</h2>
        </Rise>
        <Rise i={1} className={cx(LEAD, 'max-w-[40ch] text-muted')}>
          {d ? `${tn(d.match.home)} ${d.match.home_goals}–${d.match.away_goals} ${tn(d.match.away)}, tal como sale en la app.` : 'Un partido real, tal como sale en la app.'}
        </Rise>
      </div>
      <div className={cx(WRAP, 'grid gap-10 md:grid-cols-[7fr_5fr] md:items-center md:gap-16')}>
        {/* Una pieza cada vez, sobre el fondo de la sección: se cambia con la lista, las flechas o arrastrando */}
        <div className="flex min-h-[260px] items-center md:min-h-[460px]">
          {p ? (
            <motion.div
              key={p.name}
              data-ui
              drag="x"
              dragConstraints={{ left: 0, right: 0 }}
              dragElastic={0.18}
              onDragEnd={(_, info) => {
                if (info.offset.x < -60) go(active + 1)
                else if (info.offset.x > 60) go(active - 1)
              }}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.35, ease }}
              className="w-full cursor-grab touch-pan-y text-[14px] active:cursor-grabbing"
              aria-label={`Pieza de la ficha: ${p.name}`}
            >
              {p.body}
            </motion.div>
          ) : (
            <div className="skeleton h-80 w-full rounded-[14px]" />
          )}
        </div>
        <div>
          <ul className="space-y-1" aria-label="Piezas de la ficha de un partido">
            {panels.map((pn, i) => (
              <li key={pn.name}>
                <button
                  onClick={() => go(i)}
                  aria-current={i === active}
                  className="group block w-full py-3 text-left"
                >
                  <span className={cx('block text-[24px] leading-tight font-medium tracking-[-0.01em] transition-colors duration-150', i === active ? 'text-fg' : 'text-subtle group-hover:text-fg')}>{pn.name}</span>
                  {i === active && <span className="mt-1 block text-[16px] leading-[1.55] text-muted">{pn.text}</span>}
                </button>
              </li>
            ))}
          </ul>
          <div className="mt-6 flex gap-2">
            {[
              { icon: <ArrowLeft size={18} />, to: active - 1, label: 'Anterior' },
              { icon: <ArrowRight size={18} />, to: active + 1, label: 'Siguiente' },
            ].map((b) => (
              <button key={b.label} onClick={() => go(b.to)} aria-label={b.label} className="grid size-12 place-items-center rounded-[8px] bg-surface-3 text-fg transition-transform duration-150 hover:bg-[color-mix(in_srgb,var(--surface-3)_70%,var(--text))] active:scale-95">
                {b.icon}
              </button>
            ))}
          </div>
        </div>
      </div>
    </section>
  )
}

/* ---------------------------------------------------------------- cómo se lee una ficha */

function MarginNotes({ d }: { d: MatchDetail | undefined }) {
  const [focus, setFocus] = useState<NoteKey | null>(null)
  const note = (n: (typeof NOTES)[number], i: number) => (
    <Rise key={n.key} i={i} y={16}>
      <button
        onMouseEnter={() => setFocus(n.key)}
        onMouseLeave={() => setFocus(null)}
        onFocus={() => setFocus(n.key)}
        onBlur={() => setFocus(null)}
        className={cx('block w-full max-w-[26ch] rounded-[6px] text-left transition-colors', n.side === 'l' ? 'lg:ml-auto lg:text-right' : '')}
      >
        <span className={cx('block text-[20px] font-medium transition-colors', focus === n.key ? 'text-accent' : 'text-fg')}>{n.title}</span>
        <span className="mt-1 block text-[16px] leading-[1.5] text-muted">{n.text}</span>
      </button>
    </Rise>
  )
  const side = (s: 'l' | 'r') => NOTES.filter((n) => n.side === s)
  return (
    <section className={cx('bg-bg py-28 md:py-44', PAD)}>
      <div className={WRAP}>
        <Rise className="mb-14 lg:mb-20">
          <h2 className={cx(H2, 'max-w-[14ch]')}>Cómo se lee una ficha.</h2>
        </Rise>
        {/* Escritorio: notas alineadas con la parte de la ficha que explican */}
        <div className="hidden grid-cols-[1fr_400px_1fr] gap-12 lg:grid">
          {(['l', 'r'] as const).map((s) => (
            <div key={s} className={cx('relative', s === 'r' && 'order-3')}>
              {side(s).map((n, i) => (
                <div key={n.key} className="absolute inset-x-0" style={{ top: PART_TOP[n.key] - 2 }}>
                  {note(n, i)}
                </div>
              ))}
            </div>
          ))}
          <div className="order-2">{d ? <MatchFile d={d} focus={focus} /> : <div className="skeleton h-[800px] rounded-[12px]" />}</div>
        </div>
        {/* Móvil y tableta: la ficha y debajo sus seis notas */}
        <div className="lg:hidden">
          {d ? <div className="mx-auto max-w-[400px]"><MatchFile d={d} focus={focus} /></div> : <div className="skeleton h-[800px] rounded-[12px]" />}
          <div className="mx-auto mt-10 grid max-w-[560px] grid-cols-2 gap-x-6 gap-y-8">{NOTES.map((n, i) => note({ ...n, side: 'r' }, i))}</div>
        </div>
      </div>
    </section>
  )
}

/* ---------------------------------------------------------------- fuentes y cifras */

function Sources({ meta }: { meta: Meta | undefined }) {
  const { data: mk } = useApi<Markets>(api.markets)
  const tiles: { big: string; small: string }[] = [
    { big: 'Football-Data', small: 'Resultados y cuotas medias de las casas' },
    { big: 'ESPN', small: 'Estadísticas, alineaciones y calendario' },
    { big: 'PitchAPI', small: 'Tiros con xG, momentum y mapas de calor' },
    { big: 'Transfermarkt', small: 'Valores de mercado de cada plantilla' },
    { big: 'Polymarket', small: 'Precios del mercado de predicción' },
    { big: meta ? int(meta.counts.matches) : '–', small: 'partidos unidos, cero marcadores discrepantes' },
    { big: meta ? int(meta.counts.shots) : '–', small: 'tiros con su xG' },
    { big: meta ? int(meta.counts.teams) : '–', small: 'equipos de cinco ligas, de 2021/22 a hoy' },
    { big: mk ? int(mk.n) : '–', small: 'partidos con precio en Polymarket' },
    { big: mk ? pct(mk.all_books_mean, 1) : '–', small: 'margen medio de las casas' },
  ]
  return (
    <section id="fuentes" className={cx('scroll-mt-0 bg-surface-1 py-28 md:py-40', PAD)}>
      <div className={cx(WRAP, 'grid grid-cols-2 gap-1.5 md:grid-cols-4 md:gap-2')}>
        <Rise className="col-span-2 flex min-h-[160px] flex-col justify-between rounded-[12px] bg-accent p-6 text-[#0c0d0f] md:min-h-[230px] md:p-8">
          <h2 className={H2}>Cinco fuentes, un partido.</h2>
          <p className="max-w-[40ch] text-[16px] leading-[1.5]">Unidas partido a partido. Las variables solo usan partidos anteriores al que se predice, y hay tests que lo comprueban.</p>
        </Rise>
        {tiles.map((t, i) => (
          <Rise key={t.small} i={(i % 4) + 1} y={16} className="flex min-h-[150px] flex-col justify-end gap-2 rounded-[12px] bg-surface-2 p-5 md:min-h-[230px] md:p-6">
            <span className="text-[clamp(20px,2.2vw,32px)] leading-[1.05] font-semibold tracking-[-0.02em] tnum">{t.big}</span>
            <span className="text-[16px] leading-[1.45] text-muted">{t.small}</span>
          </Rise>
        ))}
      </div>
    </section>
  )
}

/* ---------------------------------------------------------------- cierre */

function Closing() {
  return (
    <section className="overflow-hidden bg-bg py-28 md:py-40">
      <div className="grid grid-cols-2 gap-2 md:grid-cols-12 md:gap-3">
        <Rise className="relative order-2 h-[140px] overflow-hidden rounded-[12px] md:order-1 md:col-span-2 md:-ml-6 md:h-[380px]">
          <img src={estadioNoche} alt="Grada llena bajo los focos en un estadio de noche" loading="lazy" width={1200} height={1600} className="size-full object-cover" />
        </Rise>
        <Rise i={1} className="order-1 col-span-2 flex min-h-[320px] flex-col justify-center rounded-[12px] bg-accent p-7 text-[#0c0d0f] md:order-2 md:col-span-8 md:h-[380px] md:p-12">
          <h2 className={H2}>La jornada, sin margen.</h2>
          <p className="mt-4 max-w-[44ch] text-[20px] leading-[1.55]">LaLiga, Premier, Serie A, Bundesliga y Ligue 1, con datos de esta misma semana. Sin dinero real: solo análisis.</p>
          <div className="mt-8"><Button to="/hoy" tone="ink">Abrir la app</Button></div>
        </Rise>
        <Rise i={2} className="relative order-3 h-[140px] overflow-hidden rounded-[12px] md:col-span-2 md:-mr-6 md:h-[380px]">
          <img src={campoFocos} alt="Campo de césped artificial iluminado por focos al pie de una montaña nevada" loading="lazy" width={1024} height={732} className="breathe size-full object-cover" />
        </Rise>
      </div>
    </section>
  )
}

function Footer() {
  return (
    <footer className={cx('bg-bg pt-[24svh] pb-8', PAD)}>
      <div className={cx(WRAP, 'grid gap-2 text-[16px] md:grid-cols-[1fr_auto_1fr] md:items-baseline md:gap-6')}>
        <span className="text-muted">Halfline · Probabilidades 1X2 frente al mercado</span>
        <nav className="flex flex-wrap gap-6">
          <Link to="/hoy" className="hover:text-accent">Hoy</Link>
          <Link to="/modelo" className="hover:text-accent">Modelo</Link>
          <Link to="/datos" className="hover:text-accent">Datos</Link>
        </nav>
        <span className="text-muted md:text-right">{new Date().getFullYear()} · Sin dinero real</span>
      </div>
      <p className={cx(WRAP, 'mt-6 text-[13px] leading-[1.5] text-muted')}><span className="block max-w-[60ch]">
        Fotografías: «Interior of a football stadium at night» de Jeff Chi (CC0, WordPress Photo Directory); «Turf soccer pitch illuminated floodlights» (CC0, rawpixel).</span>
      </p>
    </footer>
  )
}

/* ---------------------------------------------------------------- página */

export default function Landing() {
  const { data: meta } = useApi<Meta>(api.meta)
  const list = useShowcaseMatches()
  const [pick, setPick] = useState(0)
  const current = list.length ? list[pick % list.length] : undefined
  const { data: d } = useApi<MatchDetail>(current ? api.match(current.match_id) : null)
  // Precarga el siguiente para que «Otro» cambie al instante
  useApi<MatchDetail>(list.length > 1 ? api.match(list[(pick + 1) % list.length].match_id) : null)

  useEffect(() => {
    document.title = 'Halfline · quita el margen, mira el partido'
  }, [])

  return (
    <div className="theme-dark min-h-dvh overflow-x-clip">
      <TopNav />
      <main>
        <Hero d={d} onNext={() => setPick((p) => p + 1)} />
        <HowItWorks d={d} />
        <PredictionMarkets />
        <Showcase d={d} />
        <MarginNotes d={d} />
        <Sources meta={meta} />
        <Closing />
      </main>
      <Footer />
      <span className="sr-only">{d ? `${tn(d.match.home)} – ${tn(d.match.away)}, ${seasonLabel(d.match.season)}` : ''}</span>
    </div>
  )
}
