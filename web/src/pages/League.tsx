import { ArrowDown, ArrowUp } from 'lucide-react'
import { useMemo, useState } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { Scatter } from '../components/charts'
import { PageHeader, useCrumbs } from '../components/shell'
import { cx, ErrorState, FormSquares, Panel, PanelHeader, Select, Skeleton, Stagger, StaggerItem, TeamBadge } from '../components/ui'
import { api, useApi, useTeams, type LeagueCode, type Meta, type TableRow, teamName as tn } from '../lib/api'
import { LEAGUES, num, seasonLabel, signed } from '../lib/format'

/** Cuatro titulares de la temporada sacados de la tabla. */
function Headlines({ rows, league, season }: { rows: TableRow[]; league: string; season: number }) {
  const by = (f: (r: TableRow) => number) => [...rows].sort((a, b) => f(b) - f(a))[0]
  const leader = rows.find((r) => r.pos === 1) ?? rows[0]
  const lucky = by((r) => r.pts - r.xpts)
  const unlucky = by((r) => r.xpts - r.pts)
  const attack = by((r) => r.xg_for / Math.max(r.played, 1))
  const tiles = [
    { label: 'Líder', team: leader, value: `${leader.pts} pts`, sub: `${leader.won}-${leader.drawn}-${leader.lost} · ${num(leader.xpts, 1)} xPts`, tone: '' },
    { label: 'Más puntos de los que merece', team: lucky, value: signed(lucky.pts - lucky.xpts, 1), sub: `${lucky.pts} pts con ${num(lucky.xpts, 1)} esperados`, tone: 'text-pos' },
    { label: 'Menos puntos de los que merece', team: unlucky, value: signed(unlucky.pts - unlucky.xpts, 1), sub: `${unlucky.pts} pts con ${num(unlucky.xpts, 1)} esperados`, tone: 'text-neg' },
    { label: 'Mejor ataque por xG', team: attack, value: num(attack.xg_for / Math.max(attack.played, 1)), sub: 'xG por partido', tone: '' },
  ]
  return (
    <div className="mb-6 grid grid-cols-2 gap-3 xl:grid-cols-4">
      {tiles.map((t) => (
        <Link
          key={t.label}
          to={`/equipos/${league}/${encodeURIComponent(t.team.team)}?temporada=${season}`}
          className="group flex flex-col rounded-panel bg-surface-1 px-4 py-4 sm:px-5 transition-[background-color,transform] hover:bg-surface-2 active:scale-[0.99]"
        >
          <span className="line-clamp-1 text-label text-muted">{t.label}</span>
          <span className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1">
            <TeamBadge team={t.team.team} size={32} />
            <span className="min-w-0 flex-1">
              <span className="block truncate text-[16px] font-semibold tracking-[-0.01em]">{tn(t.team.team)}</span>
              <span className="hidden truncate text-caption text-muted tnum sm:block">{t.sub}</span>
            </span>
            <span className={cx('num w-full text-[22px] font-semibold tracking-[-0.03em] sm:ml-auto sm:w-auto sm:text-[26px]', t.tone)}>{t.value}</span>
          </span>
        </Link>
      ))}
    </div>
  )
}

type SortKey = 'pos' | 'pts' | 'xpts' | 'xg_for' | 'xg_against' | 'xg_diff' | 'gd'

export default function League() {
  const { league = 'SP1' } = useParams() as { league: LeagueCode }
  const [params, setParams] = useSearchParams()
  const navigate = useNavigate()
  const { data: meta } = useApi<Meta>(api.meta)
  const seasons = meta?.leagues.find((l) => l.code === league)?.seasons ?? []
  const season = Number(params.get('temporada')) || seasons.at(-1)
  const { data, error } = useApi<{ rows: TableRow[] }>(season ? api.table(league, season) : null)
  const [sort, setSort] = useState<{ key: SortKey; dir: 1 | -1 }>({ key: 'pos', dir: 1 })
  const info = LEAGUES[league]
  const { crest } = useTeams()
  useCrumbs([{ label: info?.name ?? league }, { label: season ? seasonLabel(season) : '' }])

  const rows = useMemo(() => {
    if (!data) return []
    const r = [...data.rows]
    r.sort((a, b) => (a[sort.key] - b[sort.key]) * sort.dir)
    return r
  }, [data, sort])

  if (!info) return <ErrorState message="Esa liga no existe." hint="Las ligas disponibles son LaLiga, Premier League, Serie A, Bundesliga y Ligue 1." />

  const Th = ({ k, children, title }: { k: SortKey; children: React.ReactNode; title?: string }) => (
    <th className="px-2 py-2 text-right font-normal" title={title}>
      <button
        onClick={() => setSort((s) => ({ key: k, dir: s.key === k ? (-s.dir as 1 | -1) : k === 'pos' || k === 'xg_against' ? 1 : -1 }))}
        className={cx('inline-flex items-center gap-1 transition-colors hover:text-fg', sort.key === k && 'text-fg')}
      >
        {children}
        {sort.key === k && (sort.dir === 1 ? <ArrowUp size={11} /> : <ArrowDown size={11} />)}
      </button>
    </th>
  )

  const luck = (r: TableRow) => r.pts - r.xpts

  return (
    <>
      <PageHeader
        title={info.name}
        sub={season ? `Temporada ${seasonLabel(season)} · clasificación con goles esperados (xG) y puntos esperados (xPts)` : ' '}
        actions={
          <Select
            label="Temporada"
            value={season}
            onChange={(v) => setParams({ temporada: v }, { replace: true })}
            options={[...seasons].reverse().map((x) => ({ value: x, label: seasonLabel(x) }))}
          />
        }
      />
      {error && <ErrorState message="No se pudo cargar la clasificación." />}
      <Stagger>
      <StaggerItem>{data && season ? <Headlines rows={data.rows} league={league} season={season} /> : <Skeleton className="mb-6 h-[104px] w-full rounded-panel" />}</StaggerItem>
      <StaggerItem className="grid grid-cols-1 gap-6 2xl:grid-cols-[minmax(0,1fr)_480px]">
        <Panel className="overflow-x-auto">
          <table className="w-full min-w-[760px] text-label">
            <thead className="border-b border-line text-caption text-muted">
              <tr>
                <Th k="pos">#</Th>
                <th className="px-2 py-2 text-left font-normal">Equipo</th>
                <th className="px-2 py-2 text-right font-normal">PJ</th>
                <th className="px-2 py-2 text-right font-normal">G-E-P</th>
                <Th k="gd">DG</Th>
                <Th k="pts">Pts</Th>
                <Th k="xpts" title="Puntos esperados según el xG de cada partido">xPts</Th>
                <th className="px-2 py-2 text-right font-normal" title="Puntos reales menos esperados">Pts − xPts</th>
                <Th k="xg_for">xG</Th>
                <Th k="xg_against">xGA</Th>
                <Th k="xg_diff">xGD</Th>
                <th className="px-3 py-2 text-left font-normal">Últimos 5</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {!data &&
                Array.from({ length: 20 }).map((_, i) => (
                  <tr key={i}>
                    <td colSpan={12} className="px-3 py-2.5"><Skeleton className="h-4 w-full" /></td>
                  </tr>
                ))}
              {rows.map((r) => {
                const l = luck(r)
                return (
                  <tr
                    key={r.team}
                    onClick={() => navigate(`/equipos/${league}/${encodeURIComponent(r.team)}?temporada=${season}`)}
                    className="h-11 cursor-default transition-colors hover:bg-surface-2"
                  >
                    <td className="num relative w-10 px-2 text-right text-muted">
                      {/* Zona alta y zona baja: una marca de color al borde de la fila */}
                      {(r.pos <= 4 || r.pos > data!.rows.length - 3) && (
                        <span className={cx('absolute inset-y-2 left-0 w-[3px] rounded-r-full', r.pos <= 4 ? 'bg-accent' : 'bg-neg')} />
                      )}
                      {r.pos}
                    </td>
                    <td className="px-2">
                      <span className="flex items-center gap-2.5">
                        <TeamBadge team={r.team} size={20} />
                        <span className="truncate font-medium">{tn(r.team)}</span>
                      </span>
                    </td>
                    <td className="num px-2 text-right text-muted">{r.played}</td>
                    <td className="num px-2 text-right text-muted">{r.won}-{r.drawn}-{r.lost}</td>
                    <td className="num px-2 text-right text-muted">{signed(r.gd, 0)}</td>
                    <td className="num px-2 text-right font-semibold">{r.pts}</td>
                    <td className="num px-2 text-right text-muted">{num(r.xpts, 1)}</td>
                    <td className={cx('num px-2 text-right', Math.abs(l) >= 4 ? (l > 0 ? 'text-pos' : 'text-neg') : 'text-subtle')}>{signed(l, 1)}</td>
                    <td className="num px-2 text-right text-muted">{num(r.xg_for, 1)}</td>
                    <td className="num px-2 text-right text-muted">{num(r.xg_against, 1)}</td>
                    <td className="num px-2 text-right">{signed(r.xg_diff, 1)}</td>
                    <td className="px-3"><FormSquares form={r.form} size={15} /></td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </Panel>
        <Panel>
          <PanelHeader title="Ataque frente a defensa" sub="xG por partido a favor y en contra · arriba a la derecha, los mejores" />
          <div className="p-4">
            {data ? (
              <Scatter
                points={data.rows.map((r) => ({
                  id: r.team,
                  label: tn(r.team),
                  x: r.xg_for / Math.max(r.played, 1),
                  y: r.xg_against / Math.max(r.played, 1),
                  highlight: r.pos <= 4,
                  image: crest(r.team),
                }))}
                xLabel="xG a favor"
                yLabel="Mejor defensa (menos xG en contra)"
                invertY
                height={420}
                onSelect={(t) => navigate(`/equipos/${league}/${encodeURIComponent(t)}?temporada=${season}`)}
              />
            ) : (
              <Skeleton className="h-[420px] w-full" />
            )}
            <p className="mt-2 text-caption text-muted">Con aro verde, los cuatro primeros de la clasificación. Pasa el ratón por un escudo para ver el nombre.</p>
          </div>
        </Panel>
      </StaggerItem>
      </Stagger>
    </>
  )
}
