import { AnimatePresence, motion } from 'motion/react'
import { useMemo, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { Legend, TimeChart } from '../components/charts'
import { useCrumbs } from '../components/shell'
import { TeamStyleCard } from '../components/stylemap'
import { Finishing, ImpactChart, PlayerCard, SeasonShots, SquadTable, StyleProfile, TypicalXI } from '../components/team'
import { cx, ErrorState, FormSquares, Panel, PanelHeader, Select, Skeleton, Stagger, StaggerItem, Stat, Tabs, TeamBadge } from '../components/ui'
import { analysisUrl, api, prefetch, useApi, type LeagueCode, type Styles as StylesData, type TeamAnalysis, type TeamPage, teamName as tn } from '../lib/api'
import { day, LEAGUES, num, seasonLabel, signed } from '../lib/format'

export default function Team() {
  const { league = 'SP1', team = '' } = useParams() as { league: LeagueCode; team: string }
  const [params, setParams] = useSearchParams()
  const season = Number(params.get('temporada')) || undefined
  const { data: t, error } = useApi<TeamPage>(api.team(league, team, season))
  const { data: all } = useApi<{ league: LeagueCode; team: string; seasons: number[] }[]>(api.teams)
  const seasons = all?.find((x) => x.league === league && x.team === team)?.seasons ?? []
  type TeamTab = 'resumen' | 'plantilla' | 'once' | 'impacto' | 'estilo' | 'tiros'
  const tab = (params.get('tab') as TeamTab) || 'resumen'
  const switchTab = (v: TeamTab) => {
    const p = new URLSearchParams(params)
    p.set('tab', v)
    setParams(p, { replace: true })
  }
  // El análisis completo solo se pide al abrir una pestaña que lo usa
  const { data: a, error: aErr } = useApi<TeamAnalysis>(t && tab !== 'resumen' ? analysisUrl(league, team, t.season) : null)
  const [player, setPlayer] = useState<string | null>(null)
  const { data: styles } = useApi<StylesData>(tab === 'estilo' ? api.styles : null)
  const selected = a?.squad.find((p) => p.id === player) ?? null
  useCrumbs([
    { label: LEAGUES[league]?.name ?? league, to: `/ligas/${league}${t ? `?temporada=${t.season}` : ''}` },
    { label: tn(team) },
  ])

  const series = useMemo(() => {
    if (!t) return null
    // Algunos partidos no tienen hora de inicio: sin fecha no tienen sitio en el eje temporal
    const dated = t.series.filter((p) => p.kickoff)
    const s = dated.filter((p) => p.ewm_xg_for !== null)
    return {
      dates: s.map((p) => new Date(p.kickoff)),
      xgFor: s.map((p) => p.ewm_xg_for),
      xgAg: s.map((p) => p.ewm_xg_against),
      elo: dated.filter((p) => p.elo !== null),
    }
  }, [t])

  if (error) return <ErrorState message={error === 'No encontrado' ? `No hay datos de ${team}.` : 'No se pudo cargar el equipo.'} />
  if (!t || !series) return <Skeleton className="h-[600px] w-full" />

  const s = t.summary
  const last = [...t.matches].reverse()
  const form = t.matches.slice(-10).map((m) => m.result)
  const eloNow = series.elo.at(-1)?.elo ?? null
  const eloStart = series.elo.find((p) => new Date(p.kickoff).getFullYear() >= t.season)?.elo ?? null

  return (
    <>
      <h1 className="sr-only">{tn(t.team)}</h1>
      <Stagger className="mb-6 flex flex-col gap-3">
        <StaggerItem>
          <div>
            <div className="flex flex-wrap items-center gap-5 py-2">
              <motion.div initial={{ scale: 0.85, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}>
                <TeamBadge team={t.team} size={72} />
              </motion.div>
              <div className="min-w-0 flex-1">
                <div className="truncate text-[32px] leading-10 font-semibold tracking-[-0.035em] md:text-[44px] md:leading-[48px]">{tn(t.team)}</div>
                <div className="mt-1 flex flex-wrap items-center gap-3 text-[15px] text-muted">
                  <Link to={`/ligas/${league}?temporada=${t.season}`} className="transition-colors hover:text-fg">{LEAGUES[league].name}</Link>
                  <span className="text-subtle">·</span>
                  <span>Temporada {seasonLabel(t.season)}</span>
                  <FormSquares form={form} size={16} />
                </div>
              </div>
              {seasons.length > 1 && (
                <Select
                  label="Temporada"
                  value={t.season}
                  onChange={(v) => setParams({ temporada: v }, { replace: true })}
                  options={[...seasons].reverse().map((x) => ({ value: x, label: seasonLabel(x) }))}
                />
              )}
            </div>
          </div>
        </StaggerItem>
        <StaggerItem className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-6">
          <Stat label="Puntos" value={s.pts} sub={`${s.played} partidos · ${num(s.pts / Math.max(s.played, 1))} por partido`} />
          <Stat label="Goles" value={`${s.gf}–${s.ga}`} sub={`diferencia ${signed(s.gf - s.ga, 0)}`} />
          <Stat label="xG a favor" value={num(s.xg_for, 1)} sub={`${num(s.xg_for / Math.max(s.played, 1))} por partido`} />
          <Stat label="xG en contra" value={num(s.xg_against, 1)} sub={`${num(s.xg_against / Math.max(s.played, 1))} por partido`} />
          <Stat
            label="Goles − xG"
            value={signed(s.gf - s.xg_for, 1)}
            tone={s.gf - s.xg_for > 0 ? 'pos' : 'neg'}
            sub={s.gf - s.xg_for > 0 ? 'marca más de lo esperado' : 'marca menos de lo esperado'}
          />
          <Stat label="Elo" value={eloNow ? Math.round(eloNow) : '–'} sub={eloNow && eloStart ? `${signed(eloNow - eloStart, 0)} esta temporada` : undefined} />
        </StaggerItem>
      </Stagger>

      <div className="mb-6">
        <Tabs
          id="team"
          value={tab}
          onChange={(v) => {
            const p = new URLSearchParams(params)
            if (v === 'resumen') p.delete('tab')
            else p.set('tab', v)
            setParams(p, { replace: true })
          }}
          tabs={[
            { value: 'resumen', label: 'Resumen' },
            { value: 'plantilla', label: 'Plantilla' },
            { value: 'once', label: 'Once tipo' },
            { value: 'impacto', label: 'Impacto' },
            { value: 'estilo', label: 'Estilo' },
            { value: 'tiros', label: 'Tiros' },
          ]}
        />
      </div>
      {tab !== 'resumen' && !a && (aErr ? <ErrorState message="No se pudo cargar el análisis." /> : <Skeleton className="h-[520px] w-full" />)}
      <AnimatePresence mode="wait">
        <motion.div
          key={tab}
          initial={{ opacity: 0, y: 4 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, transition: { duration: 0.08 } }}
          transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
        >
      {tab === 'resumen' && (
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1fr)_400px]">
        <div className="flex flex-col gap-6">
          <Panel>
            <PanelHeader
              title="Rendimiento subyacente"
              sub="xG a favor y en contra, media móvil exponencial (semivida de 5 partidos), todo el historial"
              aside={<Legend items={[{ label: 'xG a favor', color: 'var(--accent)' }, { label: 'xG en contra', color: 'var(--neg)' }]} />}
            />
            <div className="p-4">
              <TimeChart
                dates={series.dates}
                series={[
                  { key: 'for', label: 'xG a favor', color: 'var(--accent)', values: series.xgFor, area: true },
                  { key: 'ag', label: 'xG en contra', color: 'var(--neg)', values: series.xgAg },
                ]}
                height={260}
              />
            </div>
          </Panel>
          <Panel>
            <PanelHeader title="Elo" sub="Rating antes de cada partido · 1.500 = equipo medio" />
            <div className="p-4">
              <TimeChart
                dates={series.elo.map((p) => new Date(p.kickoff))}
                series={[{ key: 'elo', label: 'Elo', color: 'var(--text)', values: series.elo.map((p) => p.elo), area: true }]}
                baseline={{ value: 1500, label: 'media' }}
                format={(v) => Math.round(v).toLocaleString('es-ES')}
                height={200}
              />
            </div>
          </Panel>
        </div>

        <Panel className="flex max-h-[760px] flex-col">
          <PanelHeader title="Partidos" aside={<FormSquares form={form} size={14} />} />
          <ul className="flex-1 divide-y divide-line overflow-y-auto">
            {last.map((m) => (
              <li key={m.match_id}>
                <Link
                  to={`/partidos/${m.match_id}`}
                  onMouseEnter={() => prefetch(api.match(m.match_id))}
                  className="grid grid-cols-[20px_minmax(0,1fr)_auto] items-center gap-3 px-4 py-2 transition-colors hover:bg-surface-2"
                >
                  <FormSquares form={[m.result]} size={18} />
                  <span className="min-w-0">
                    <span className="block truncate text-label">
                      <span className="text-subtle">{m.venue === 'H' ? 'vs' : 'en'}</span> {tn(m.opponent)}
                    </span>
                    <span className="num text-caption text-subtle">
                      {day(m.kickoff)} · xG {num(m.xg_for, 1)}–{num(m.xg_against, 1)}
                    </span>
                  </span>
                  <span className={cx('num text-label font-medium', m.result === 'W' ? 'text-fg' : 'text-muted')}>
                    {m.gf}–{m.ga}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        </Panel>
      </div>
      )}
      {a && tab === 'plantilla' && (
        <div className="flex flex-col gap-6 min-[1760px]:grid min-[1760px]:grid-cols-[minmax(0,1fr)_360px]">
          <SquadTable squad={a.squad} onSelect={setPlayer} selected={player} />
          <div className="grid grid-cols-1 items-start gap-6 lg:grid-cols-2 min-[1760px]:flex min-[1760px]:flex-col">
            {selected && <PlayerCard p={selected} onClose={() => setPlayer(null)} />}
            <Finishing squad={a.squad} />
          </div>
        </div>
      )}
      {a && tab === 'once' && <TypicalXI a={a} onSelect={(id) => { setPlayer(id); switchTab('plantilla') }} />}
      {a && tab === 'impacto' && (
        <div className="grid grid-cols-1 gap-6 2xl:grid-cols-[minmax(0,1fr)_360px]">
          <ImpactChart a={a} onSelect={setPlayer} />
          {selected && <PlayerCard p={selected} onClose={() => setPlayer(null)} />}
        </div>
      )}
      {a && tab === 'estilo' && (
        <div className="flex flex-col gap-6">
          {styles && <TeamStyleCard styles={styles} league={league} team={team} season={t.season} />}
          <StyleProfile a={a} />
        </div>
      )}
      {a && tab === 'tiros' && <SeasonShots a={a} team={tn(t.team)} />}
        </motion.div>
      </AnimatePresence>
    </>
  )
}
