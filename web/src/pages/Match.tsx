import { AnimatePresence, motion } from 'motion/react'
import { useMemo, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { XgRace } from '../components/charts'
import { Heatmap, Lineups, Momentum, OUTCOME_LABEL, ShotLegend, ShotMap } from '../components/pitch'
import { PageHeader, useCrumbs } from '../components/shell'
import {
  Badge,
  cx,
  ErrorState,
  FormSquares,
  Panel,
  PanelHeader,
  ProbBar,
  Segmented,
  Skeleton,
  Tabs,
  TeamBadge,
  TeamLink,
} from '../components/ui'
import { api, teamColor, useApi, type MatchDetail, type Probs, type Side, teamName as tn } from '../lib/api'
import { exampleModel } from '../lib/example'
import { date, day, LEAGUES, num, pct, pp, seasonLabel, time } from '../lib/format'

type Tab = 'resumen' | 'tiros' | 'momentum' | 'alineaciones' | 'calor'

/* ---------------------------------------------------------------- cabecera */

function Scoreboard({ d }: { d: MatchDetail }) {
  const m = d.match
  const goals = (side: Side) =>
    d.events
      .filter((e) => e.type === 'goal' && e.side === side)
      .map((e) => `${e.player ?? ''} ${e.minute}${e.added ? `+${e.added}` : ''}′${e.penalty ? ' (p)' : ''}${e.own_goal ? ' (p.p.)' : ''}`)
  const out: keyof Probs = m.home_goals > m.away_goals ? 'home' : m.home_goals < m.away_goals ? 'away' : 'draw'
  const outLabel = out === 'home' ? `victoria del ${tn(m.home)}` : out === 'away' ? `victoria del ${tn(m.away)}` : 'el empate'
  const market = d.pre_match.market.pre
  const model = d.pre_match.model
  const hx = m.home_xg ?? 0
  const ax = m.away_xg ?? 0
  const Team = ({ side }: { side: Side }) => {
    const name = side === 'home' ? m.home : m.away
    return (
      <div className={cx('flex min-w-0 flex-1 flex-col gap-3', side === 'home' ? 'items-end text-right' : 'items-start')}>
        <motion.div initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }} transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}>
          <TeamBadge team={name} size={72} />
        </motion.div>
        <TeamLink league={m.league} team={name} className="max-w-full truncate text-[20px] leading-7 font-semibold tracking-[-0.02em] md:text-[28px] md:leading-8" />
        <ul className="space-y-0.5 text-label text-muted">
          {goals(side).map((g, i) => (
            <li key={i}>{g}</li>
          ))}
        </ul>
      </div>
    )
  }
  return (
    <div className="mb-6 overflow-hidden rounded-panel bg-surface-1">
      {/* Franja con los colores de cada equipo */}
      <div className="flex h-1.5">
        <span className="flex-1" style={{ background: teamColor(m.home) ?? 'var(--home)' }} />
        <span className="flex-1" style={{ background: teamColor(m.away) ?? 'var(--away)' }} />
      </div>
      <div className="px-5 pt-6 pb-7 md:px-10">
        <div className="mb-7 flex flex-wrap items-center justify-center gap-x-3 gap-y-1 text-label text-muted">
          <Link to={`/ligas/${m.league}?temporada=${m.season}`} className="transition-colors hover:text-fg">
            {LEAGUES[m.league].name} {seasonLabel(m.season)}
          </Link>
          <span className="text-subtle">·</span>
          <span>{date(m.kickoff)} · {time(m.kickoff)}</span>
          <span className="text-subtle">·</span>
          <span>Final</span>
        </div>
        <div className="flex items-start gap-4 md:gap-12">
          <Team side="home" />
          <div className="flex flex-col items-center pt-3">
            <span className="mask-line">
              <motion.span
                className="num block text-[56px] leading-none font-semibold tracking-[-0.05em] md:text-[96px]"
                initial={{ y: '100%' }}
                animate={{ y: 0 }}
                transition={{ duration: 0.7, ease: [0.16, 1, 0.3, 1] }}
              >
                {m.home_goals}
                <span className="mx-2 text-subtle md:mx-3">–</span>
                {m.away_goals}
              </motion.span>
            </span>
          </div>
          <Team side="away" />
        </div>
        {m.home_xg !== null && (
          <div className="mx-auto mt-8 max-w-[560px]">
            <div className="num mb-2 flex justify-between text-label">
              <span className="font-semibold text-home">{num(hx)} xG</span>
              <span className="text-muted">Goles esperados</span>
              <span className="font-semibold text-away">{num(ax)} xG</span>
            </div>
            <div className="flex h-2 gap-[3px]">
              <motion.span className="rounded-l-full bg-home" initial={{ flexGrow: 1 }} animate={{ flexGrow: hx || 0.01 }} transition={{ duration: 0.8, delay: 0.2, ease: [0.16, 1, 0.3, 1] }} />
              <motion.span className="rounded-r-full bg-away" initial={{ flexGrow: 1 }} animate={{ flexGrow: ax || 0.01 }} transition={{ duration: 0.8, delay: 0.2, ease: [0.16, 1, 0.3, 1] }} />
            </div>
          </div>
        )}
        {market && (
          <p className="mx-auto mt-6 max-w-[620px] text-center text-[15px] leading-6 text-muted">
            Antes del partido, el mercado daba un <span className="num font-semibold text-fg">{pct(market[out])}</span> a {outLabel}
            {model && (
              <>
                {' '}y el modelo, un <span className="num font-semibold text-fg">{pct(model.probs[out])}</span>
              </>
            )}
            .
          </p>
        )}
      </div>
    </div>
  )
}

/* ---------------------------------------------------------------- resumen */

/** Dot plot: modelo (punto) frente a mercado (aro) por resultado. */
function ModelVsMarket({ model, market, example, name }: { model: Probs; market: Probs | null; example: boolean; name?: string }) {
  const rows: { k: keyof Probs; label: string; color: string }[] = [
    { k: 'home', label: 'Local', color: 'var(--home)' },
    { k: 'draw', label: 'Empate', color: 'var(--draw)' },
    { k: 'away', label: 'Visitante', color: 'var(--away)' },
  ]
  return (
    <Panel>
      <PanelHeader
        title="Antes del partido"
        sub="Modelo frente a cuotas medias pre-cierre sin margen"
        aside={example ? <Badge tone="warn">Modelo de ejemplo</Badge> : <Badge tone="accent">{name} · fuera de muestra</Badge>}
      />
      <div className="space-y-5 p-4">
        <div className="space-y-2">
          <div className="flex items-center justify-between text-caption text-subtle">
            <span>{name ?? 'Modelo'}</span>
            <span className="num text-muted">{pct(model.home)} · {pct(model.draw)} · {pct(model.away)}</span>
          </div>
          <ProbBar probs={model} height={10} />
          {market && (
            <>
              <div className="flex items-center justify-between pt-1 text-caption text-subtle">
                <span>Mercado</span>
                <span className="num text-muted">{pct(market.home)} · {pct(market.draw)} · {pct(market.away)}</span>
              </div>
              <ProbBar probs={market} height={10} muted />
            </>
          )}
        </div>
        {market && (
          <div className="space-y-3 border-t border-line pt-4">
            {rows.map((r) => {
              const a = model[r.k]
              const b = market[r.k]
              const lo = Math.min(a, b)
              const hi = Math.max(a, b)
              const delta = a - b
              return (
                <div key={r.k} className="grid grid-cols-[72px_minmax(0,1fr)_64px] items-center gap-3">
                  <span className="text-label text-muted">{r.label}</span>
                  <div className="relative h-5">
                    <div className="absolute inset-x-0 top-1/2 h-px bg-line" />
                    <motion.div
                      className="absolute top-1/2 h-[2px] -translate-y-1/2 rounded-full"
                      style={{ background: r.color, opacity: 0.45 }}
                      initial={{ left: `${b * 100}%`, width: 0 }}
                      animate={{ left: `${lo * 100}%`, width: `${(hi - lo) * 100}%` }}
                      transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
                    />
                    <div className="absolute top-1/2 size-3 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 bg-surface-1" style={{ left: `${b * 100}%`, borderColor: 'var(--text-subtle)' }} />
                    <motion.div
                      className="absolute top-1/2 size-3 -translate-x-1/2 -translate-y-1/2 rounded-full"
                      style={{ background: r.color }}
                      initial={{ left: `${b * 100}%` }}
                      animate={{ left: `${a * 100}%` }}
                      transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
                    />
                  </div>
                  <span className={cx('num text-right text-label', Math.abs(delta) >= 0.03 ? (delta > 0 ? 'text-pos' : 'text-neg') : 'text-subtle')}>
                    {pp(delta)}
                  </span>
                </div>
              )
            })}
            <p className="flex items-center gap-4 pt-1 text-caption text-subtle">
              <span className="flex items-center gap-1.5"><span className="size-2.5 rounded-full bg-muted" /> Modelo</span>
              <span className="flex items-center gap-1.5"><span className="size-2.5 rounded-full border-2 border-subtle" /> Mercado</span>
            </p>
          </div>
        )}
      </div>
    </Panel>
  )
}

function PreMatchForm({ d }: { d: MatchDetail }) {
  const rows = [
    { label: 'Elo', h: d.pre_match.home.elo, a: d.pre_match.away.elo, f: (v: number) => Math.round(v).toString() },
    { label: 'xG a favor (últ. 5)', h: d.pre_match.home.form.xg_for, a: d.pre_match.away.form.xg_for, f: (v: number) => num(v) },
    { label: 'xG en contra (últ. 5)', h: d.pre_match.home.form.xg_against, a: d.pre_match.away.form.xg_against, f: (v: number) => num(v) },
    { label: 'Puntos por partido (últ. 5)', h: d.pre_match.home.form.points, a: d.pre_match.away.form.points, f: (v: number) => num(v) },
    { label: 'Días de descanso', h: d.pre_match.home.rest_days, a: d.pre_match.away.rest_days, f: (v: number) => num(v, 0) },
  ]
  return (
    <Panel>
      <PanelHeader title="Forma previa" sub="Calculada solo con partidos anteriores" />
      <div className="grid grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] items-center gap-x-4 gap-y-3 p-4">
        <span className="truncate text-label font-medium">{tn(d.match.home)}</span>
        <span />
        <span className="truncate text-right text-label font-medium">{tn(d.match.away)}</span>
        <FormSquares form={d.pre_match.home.last5} />
        <span className="text-center text-caption text-subtle">Últimos 5</span>
        <span className="justify-self-end"><FormSquares form={d.pre_match.away.last5} /></span>
        {rows.map((r) => {
          const better = r.h !== null && r.a !== null && r.h !== r.a ? (r.label.includes('contra') ? (r.h < r.a ? 'h' : 'a') : r.h > r.a ? 'h' : 'a') : null
          return (
            <div key={r.label} className="contents">
              <span className={cx('num text-label', better === 'h' ? 'text-fg' : 'text-muted')}>{r.h !== null ? r.f(r.h) : '–'}</span>
              <span className="text-center text-caption text-subtle">{r.label}</span>
              <span className={cx('num text-right text-label', better === 'a' ? 'text-fg' : 'text-muted')}>{r.a !== null ? r.f(r.a) : '–'}</span>
            </div>
          )
        })}
      </div>
    </Panel>
  )
}

function StatsCompare({ d }: { d: MatchDetail }) {
  const groups = useMemo(() => {
    const g = new Map<string, MatchDetail['stats']>()
    d.stats.forEach((s) => g.set(s.group, [...(g.get(s.group) ?? []), s]))
    return [...g.entries()]
  }, [d.stats])
  return (
    <Panel>
      <PanelHeader title="Estadísticas" />
      <div className="divide-y divide-line">
        {groups.map(([group, stats]) => (
          <div key={group} className="space-y-3 px-4 py-4">
            <div className="text-caption text-subtle">{group}</div>
            {stats.map((s) => {
              const h = s.home ?? 0
              const a = s.away ?? 0
              const total = h + a || 1
              const decimals = s.label.startsWith('xG') ? 2 : 0
              return (
                <div key={s.key} className="space-y-1.5">
                  <div className="flex items-baseline justify-between text-label">
                    <span className={cx('num', h > a ? 'font-medium text-fg' : 'text-muted')}>{s.home === null ? '–' : num(s.home, decimals)}</span>
                    <span className="text-caption text-muted">{s.label}</span>
                    <span className={cx('num', a > h ? 'font-medium text-fg' : 'text-muted')}>{s.away === null ? '–' : num(s.away, decimals)}</span>
                  </div>
                  <div className="flex h-1 gap-1">
                    <div className="flex flex-1 justify-end overflow-hidden rounded-full bg-surface-3">
                      <motion.div className="h-full rounded-full" style={{ background: 'var(--home)', opacity: h >= a ? 1 : 0.45 }} initial={{ width: 0 }} animate={{ width: `${(h / total) * 100}%` }} transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }} />
                    </div>
                    <div className="flex flex-1 overflow-hidden rounded-full bg-surface-3">
                      <motion.div className="h-full rounded-full" style={{ background: 'var(--away)', opacity: a >= h ? 1 : 0.45 }} initial={{ width: 0 }} animate={{ width: `${(a / total) * 100}%` }} transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }} />
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        ))}
      </div>
    </Panel>
  )
}

function Summary({ d }: { d: MatchDetail }) {
  const market = d.pre_match.market.pre
  const real = d.pre_match.model
  const model = real?.probs ?? exampleModel(d.match.match_id, market)
  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
      <div className="flex flex-col gap-6">
        <ModelVsMarket model={model} market={market} example={!real} name={real?.name} />
        <PreMatchForm d={d} />
        {d.advanced && <Advanced d={d} />}
      </div>
      <StatsCompare d={d} />
    </div>
  )
}

function Advanced({ d }: { d: MatchDetail }) {
  const a = d.advanced!
  const rows: { k: string; label: string; digits: number; hint: string }[] = [
    { k: 'xt', label: 'xT generado', digits: 2, hint: 'Amenaza esperada: valor añadido al mover el balón' },
    { k: 'vaep', label: 'VAEP', digits: 2, hint: 'Valor de las acciones según cambian la probabilidad de marcar y encajar' },
    { k: 'field_tilt', label: 'Field tilt %', digits: 0, hint: 'Cuota de acciones en el último tercio' },
    { k: 'ppda', label: 'PPDA', digits: 1, hint: 'Pases rivales por acción defensiva: menos es presionar más' },
    { k: 'progressive_passes', label: 'Pases progresivos', digits: 0, hint: '' },
    { k: 'progressive_carries', label: 'Conducciones progresivas', digits: 0, hint: '' },
    { k: 'box_entries', label: 'Entradas al área', digits: 0, hint: '' },
    { k: 'high_turnovers', label: 'Recuperaciones altas', digits: 0, hint: '' },
  ]
  return (
    <Panel>
      <PanelHeader title="Analítica avanzada" sub="Valor de posesión, presión y progresión" />
      <table className="w-full text-label">
        <tbody className="divide-y divide-line">
          {rows.map((r) => (
            <tr key={r.k} title={r.hint || undefined}>
              <td className="num w-20 px-4 py-2 text-muted">{num(a.home[r.k], r.digits)}</td>
              <td className="px-2 py-2 text-center text-caption text-subtle">{r.label}</td>
              <td className="num w-20 px-4 py-2 text-right text-muted">{num(a.away[r.k], r.digits)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </Panel>
  )
}

/* ---------------------------------------------------------------- tiros */

function Shots({ d }: { d: MatchDetail }) {
  const [active, setActive] = useState<number | null>(null)
  const [filter, setFilter] = useState<'all' | Side>('all')
  const shots = d.shots
  const visible = shots.map((s, i) => ({ s, i })).filter(({ s }) => filter === 'all' || s.side === filter)
  const tally = (side: Side) => {
    const ss = shots.filter((s) => s.side === side)
    return { n: ss.length, xg: ss.reduce((a, s) => a + s.xg, 0), g: ss.filter((s) => s.outcome === 'goal').length }
  }
  const th = tally('home')
  const ta = tally('away')
  return (
    <div className="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1fr)_340px]">
      <div className="flex min-w-0 flex-col gap-6">
      <Panel>
        <PanelHeader
          title="Mapa de tiros"
          sub={
            <>
              <span className="text-home">{tn(d.match.home)}</span> {th.n} tiros · {num(th.xg)} xG · {th.g} goles
              <span className="mx-2">/</span>
              <span className="text-away">{tn(d.match.away)}</span> {ta.n} tiros · {num(ta.xg)} xG · {ta.g} goles
            </>
          }
        />
        <div className="p-4">
          <ShotMap
            shots={filter === 'all' ? shots : shots.map((s) => (s.side === filter ? s : { ...s, xg: 0 }))}
            homeName={tn(d.match.home)}
            awayName={tn(d.match.away)}
            active={active}
            onActive={setActive}
          />
          <div className="mt-4">
            <ShotLegend />
          </div>
        </div>
      </Panel>
      <Panel>
        <PanelHeader title="Carrera de xG" sub="xG acumulado minuto a minuto · los puntos son goles" />
        <div className="p-4">
          <XgRace shots={shots} homeName={tn(d.match.home)} awayName={tn(d.match.away)} />
        </div>
      </Panel>
      </div>
      <Panel className="flex max-h-[900px] flex-col self-start">
        <PanelHeader
          title="Tiros"
          aside={
            <Segmented
              id="shots"
              value={filter}
              onChange={setFilter}
              options={[
                { value: 'all', label: 'Todos' },
                { value: 'home', label: 'Local' },
                { value: 'away', label: 'Visit.' },
              ]}
            />
          }
        />
        <ul className="flex-1 divide-y divide-line overflow-y-auto">
          {visible
            .sort((a, b) => a.s.minute - b.s.minute)
            .map(({ s, i }) => (
              <li
                key={i}
                onMouseEnter={() => setActive(i)}
                onMouseLeave={() => setActive(null)}
                className={cx('grid grid-cols-[36px_minmax(0,1fr)_auto] items-center gap-3 px-4 py-2 transition-colors', active === i && 'bg-surface-2')}
              >
                <span className="num text-caption text-subtle">{s.minute}′</span>
                <span className="min-w-0">
                  <span className="flex items-center gap-2 truncate text-label">
                    <span className="size-1.5 shrink-0 rounded-full" style={{ background: s.side === 'home' ? 'var(--home)' : 'var(--away)' }} />
                    <span className="truncate">{s.player}</span>
                  </span>
                  <span className={cx('text-caption', s.outcome === 'goal' ? 'text-accent' : 'text-subtle')}>{OUTCOME_LABEL[s.outcome]}</span>
                </span>
                <span className="num text-label">{num(s.xg)}</span>
              </li>
            ))}
        </ul>
      </Panel>
    </div>
  )
}

/* ---------------------------------------------------------------- calor */

function Heatmaps({ d }: { d: MatchDetail }) {
  const h = d.heatmaps!
  const [who, setWho] = useState<string>('team-home')
  const players = h.players
  const selected = who.startsWith('team-')
    ? { cells: who === 'team-home' ? h.teams.home : h.teams.away, side: (who === 'team-home' ? 'home' : 'away') as Side, label: tn(who === 'team-home' ? d.match.home : d.match.away), actions: null as number | null }
    : (() => {
        const p = players.find((p) => `p-${p.name}` === who)!
        return { cells: p.cells, side: p.side, label: p.name, actions: p.actions }
      })()
  return (
    <div className="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1fr)_300px]">
      <Panel>
        <PanelHeader
          title={selected.label}
          sub={<>Zonas de actuación · ataca hacia la derecha{selected.actions !== null && <> · {selected.actions} acciones</>}</>}
        />
        <div className="p-4">
          <AnimatePresence mode="wait">
            <motion.div key={who} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.15 }}>
              <Heatmap cells={selected.cells} grid={h.grid} color={selected.side === 'home' ? 'var(--home)' : 'var(--away)'} />
            </motion.div>
          </AnimatePresence>
        </div>
      </Panel>
      <Panel className="flex max-h-[560px] flex-col">
        <PanelHeader title="Equipo o jugador" />
        <ul className="flex-1 overflow-y-auto p-1.5">
          {(['home', 'away'] as Side[]).map((side) => (
            <li key={side}>
              <button
                onClick={() => setWho(`team-${side}`)}
                className={cx('flex h-8 w-full items-center gap-2 rounded-ctl px-2.5 text-label font-medium', who === `team-${side}` ? 'bg-surface-3 text-fg' : 'text-muted hover:bg-surface-2')}
              >
                <span className="size-2 rounded-full" style={{ background: side === 'home' ? 'var(--home)' : 'var(--away)' }} />
                {tn(side === 'home' ? d.match.home : d.match.away)} · equipo
              </button>
            </li>
          ))}
          <li className="mx-2.5 my-1.5 h-px bg-line" />
          {players.map((p) => (
            <li key={p.name}>
              <button
                onClick={() => setWho(`p-${p.name}`)}
                className={cx('flex h-8 w-full items-center gap-2 rounded-ctl px-2.5 text-label', who === `p-${p.name}` ? 'bg-surface-3 text-fg' : 'text-muted hover:bg-surface-2')}
              >
                <span className="num w-5 text-right text-caption text-subtle">{p.number}</span>
                <span className="size-1.5 rounded-full" style={{ background: p.side === 'home' ? 'var(--home)' : 'var(--away)' }} />
                <span className="truncate">{p.name}</span>
                <span className="num ml-auto text-caption text-subtle">{p.actions}</span>
              </button>
            </li>
          ))}
        </ul>
      </Panel>
    </div>
  )
}

/* ---------------------------------------------------------------- página */

function MatchSkeleton() {
  return (
    <div className="space-y-6">
      <Skeleton className="h-44 w-full" />
      <Skeleton className="h-10 w-96" />
      <div className="grid grid-cols-2 gap-6">
        <Skeleton className="h-96" />
        <Skeleton className="h-96" />
      </div>
    </div>
  )
}

export default function Match() {
  const { id = '' } = useParams()
  const [params, setParams] = useSearchParams()
  const tab = (params.get('tab') as Tab) || 'resumen'
  const { data: d, error } = useApi<MatchDetail>(api.match(id))
  useCrumbs(
    d
      ? [
          { label: LEAGUES[d.match.league].name, to: `/ligas/${d.match.league}?temporada=${d.match.season}` },
          { label: seasonLabel(d.match.season), to: `/partidos?liga=${d.match.league}&temporada=${d.match.season}` },
          { label: `${tn(d.match.home)} – ${tn(d.match.away)}` },
        ]
      : [{ label: 'Partidos', to: '/partidos' }, { label: '…' }],
  )
  if (error) return <ErrorState message={error === 'No encontrado' ? 'Este partido no existe.' : 'No se pudo cargar el partido.'} />
  if (!d) return <MatchSkeleton />
  const setTab = (t: Tab) => setParams(t === 'resumen' ? {} : { tab: t }, { replace: true })
  return (
    <>
      <PageHeader title={<span className="sr-only">{tn(d.match.home)} – {tn(d.match.away)}</span>} />
      <div className="-mt-6">
        <Scoreboard d={d} />
      </div>
      <div className="mb-6">
        <Tabs
          id="match"
          value={tab}
          onChange={setTab}
          tabs={[
            { value: 'resumen', label: 'Resumen' },
            { value: 'tiros', label: `Tiros · ${d.shots.length}`, disabled: !d.shots.length },
            { value: 'momentum', label: 'Momentum', disabled: !d.momentum.length },
            { value: 'alineaciones', label: 'Alineaciones', disabled: !d.lineups },
            { value: 'calor', label: 'Mapas de calor', disabled: !d.heatmaps, hint: d.heatmaps ? undefined : 'No disponible para este partido' },
          ]}
        />
      </div>
      <AnimatePresence mode="wait">
        <motion.div
          key={tab}
          initial={{ opacity: 0, y: 4 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, transition: { duration: 0.08 } }}
          transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
        >
          {tab === 'resumen' && <Summary d={d} />}
          {tab === 'tiros' && <Shots d={d} />}
          {tab === 'momentum' && (
            <Panel>
              <PanelHeader title="Momentum" sub={<>Dominio minuto a minuto · arriba <span className="text-home">{tn(d.match.home)}</span>, abajo <span className="text-away">{tn(d.match.away)}</span></>} />
              <div className="p-4 md:p-6">
                <Momentum points={d.momentum} events={d.events} />
              </div>
            </Panel>
          )}
          {tab === 'alineaciones' && d.lineups && (
            <Panel>
              <PanelHeader
                title="Alineaciones iniciales"
                sub={
                  <>
                    <span className="text-home">{tn(d.match.home)}</span> {d.lineups.home.formation}
                    {d.lineups.home.coach && <> ({d.lineups.home.coach})</>} · <span className="text-away">{tn(d.match.away)}</span> {d.lineups.away.formation}
                    {d.lineups.away.coach && <> ({d.lineups.away.coach})</>}
                  </>
                }
              />
              <div className="p-4 md:p-6">
                <Lineups home={d.lineups.home} away={d.lineups.away} />
              </div>
            </Panel>
          )}
          {tab === 'calor' && d.heatmaps && <Heatmaps d={d} />}
        </motion.div>
      </AnimatePresence>
      <p className="mt-6 text-caption text-subtle">
        Fuentes: PitchAPI (tiros, xG, momentum, alineaciones, mapas de calor) · Football-Data (cuotas) · {day(d.match.kickoff)}
      </p>
    </>
  )
}
