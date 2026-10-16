import { PageHeader, useCrumbs } from '../components/shell'
import { ArrowUpRight } from 'lucide-react'
import { Panel, PanelHeader, Stagger, StaggerItem, Stat } from '../components/ui'
import { api, useApi, type Meta } from '../lib/api'
import { date, int, LEAGUES, seasonLabel } from '../lib/format'

const SOURCES = [
  {
    name: 'Football-Data.co.uk',
    what: 'Resultados, tiros, córners, faltas, tarjetas y cuotas 1X2 de ~10 casas (pre-cierre y cierre).',
    since: '2021/22',
    url: 'https://www.football-data.co.uk',
  },
  {
    name: 'ESPN',
    what: 'Posesión, pases, centros, entradas, intercepciones y despejes; alineaciones y calendario.',
    since: '2021/22',
    url: 'https://www.espn.com/soccer/',
  },
  {
    name: 'PitchAPI',
    what: 'Tiros con coordenadas y xG, estadísticas avanzadas, momentum, alineaciones y mapas de calor.',
    since: '2021/22 · mapas de calor desde 2024/25 (Premier desde 2021/22)',
    url: 'https://pitchapi.dev',
  },
  {
    name: 'Transfermarkt (dcaribou)',
    what: 'Valores de mercado de jugadores, traspasos y plantillas.',
    since: 'hasta el 6 jul 2026',
    url: 'https://github.com/dcaribou/transfermarkt-datasets',
  },
  {
    name: 'Polymarket',
    what: 'Precios del mercado de predicción 1X2 antes del partido y al cierre, con su volumen.',
    since: '2025/26',
    url: 'https://polymarket.com',
  },
]

export default function Data() {
  const { data: meta } = useApi<Meta>(api.meta)
  useCrumbs([{ label: 'Datos' }])
  return (
    <>
      <PageHeader title="Datos" sub="De dónde sale cada cifra y hasta cuándo está actualizada." />
      <Stagger className="flex flex-col gap-6">
      <StaggerItem className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat label="Partidos" value={meta ? int(meta.counts.matches) : '–'} sub="unidos entre fuentes" />
        <Stat label="Equipos" value={meta ? int(meta.counts.teams) : '–'} sub="cinco grandes ligas" />
        <Stat label="Tiros con xG" value={meta ? int(meta.counts.shots) : '–'} sub="con su posición en el campo" />
        <Stat label="Último partido" value={meta ? date(meta.data_through) : '–'} sub="se actualiza cada semana" />
      </StaggerItem>
      <StaggerItem className="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1fr)_380px]">
        <Panel>
          <PanelHeader title="Fuentes" />
          <ul className="px-2 pb-2">
            {SOURCES.map((s) => (
              <li key={s.name}>
                <a
                  href={s.url}
                  target="_blank"
                  rel="noreferrer"
                  className="group grid gap-1 rounded-[10px] px-3 py-3 transition-colors hover:bg-surface-2 md:grid-cols-[220px_minmax(0,1fr)_16px] md:gap-6"
                >
                  <span className="text-[15px] font-semibold">{s.name}</span>
                  <span>
                    <span className="block text-label">{s.what}</span>
                    <span className="block text-caption text-muted">{s.since}</span>
                  </span>
                  <ArrowUpRight size={15} className="hidden text-subtle transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5 group-hover:text-fg md:block" />
                </a>
              </li>
            ))}
          </ul>
        </Panel>
        <Panel>
          <PanelHeader title="Cobertura" sub="Temporadas disponibles por liga" />
          <ul className="divide-y divide-line px-5">
            {meta?.leagues.map((l) => (
              <li key={l.code} className="flex items-center justify-between py-3 text-label">
                <span>{LEAGUES[l.code].name}</span>
                <span className="num text-muted">
                  {seasonLabel(l.seasons[0])} → {seasonLabel(l.seasons.at(-1)!)}
                </span>
              </li>
            ))}
          </ul>
          <p className="px-5 py-4 text-caption text-muted">
            2021/22 sirve de calentamiento: la forma y el Elo de cada equipo necesitan partidos previos.
          </p>
        </Panel>
      </StaggerItem>
      </Stagger>
    </>
  )
}
