import { motion } from 'motion/react'
import { Calibration, Legend } from '../components/charts'
import { PageHeader, useCrumbs } from '../components/shell'
import { cx, ErrorState, Panel, PanelHeader, Skeleton, Stagger, StaggerItem } from '../components/ui'
import { api, useApi, type ModelEval } from '../lib/api'
import { int, LEAGUES, num, pct, seasonLabel } from '../lib/format'

const ease = [0.16, 1, 0.3, 1] as const

const METRICS = [
  { k: 'logloss', label: 'Log-loss', hint: 'Penaliza la confianza equivocada.' },
  { k: 'brier', label: 'Brier', hint: 'Error cuadrático de las tres probabilidades.' },
  { k: 'rps', label: 'RPS', hint: 'Tiene en cuenta el orden local · empate · visitante.' },
] as const

const isMarket = (name: string) => name.startsWith('Mercado')

/** Todos los modelos sobre una misma pista de log-loss: cuanto más a la izquierda, mejor. */
function Ranking({ e }: { e: ModelEval }) {
  // Las frecuencias quedan tan lejos que aplastarían la escala: ya salen en el veredicto
  const rows = [...e.ranking].filter((r) => r.model !== 'Frecuencias').sort((a, b) => a.logloss - b.logloss)
  const lo = Math.floor(rows[0].logloss * 100) / 100 - 0.005
  const hi = Math.ceil(rows.at(-1)!.logloss * 100) / 100 + 0.005
  const x = (v: number) => ((v - lo) / (hi - lo)) * 100
  return (
    <ul className="space-y-1 px-5 pb-5">
      {rows.map((r, i) => {
        const shown = r.model === e.model
        const market = isMarket(r.model)
        return (
          <li key={r.model} className={cx('grid grid-cols-[minmax(0,190px)_minmax(0,1fr)_56px] items-center gap-4 rounded-[8px] px-2 py-1.5', shown && 'bg-surface-2')}>
            <span className={cx('truncate text-label', market || shown ? 'font-medium text-fg' : 'text-muted')}>
              {r.model}
              {shown && <span className="ml-2 text-caption text-accent">en la web</span>}
            </span>
            <span className="relative h-5">
              <span className="absolute inset-x-0 top-1/2 h-[2px] -translate-y-1/2 rounded-full bg-surface-3" />
              {!market && r.ci[1] > r.ci[0] && (
                <span
                  className="absolute top-1/2 h-1.5 -translate-y-1/2 rounded-full bg-line-strong"
                  style={{ left: `${x(r.logloss - (r.vs_market - r.ci[0]))}%`, width: `${x(r.logloss + (r.ci[1] - r.vs_market)) - x(r.logloss - (r.vs_market - r.ci[0]))}%` }}
                  title="Intervalo de confianza del 95 % de la diferencia con el mercado"
                />
              )}
              <motion.span
                className="absolute top-1/2 size-3.5 -translate-x-1/2 -translate-y-1/2 rounded-full"
                style={{ background: market ? 'var(--accent)' : shown ? 'var(--text)' : 'var(--text-subtle)' }}
                initial={{ left: '100%', opacity: 0 }}
                animate={{ left: `${x(r.logloss)}%`, opacity: 1 }}
                transition={{ duration: 0.8, delay: 0.15 + i * 0.04, ease }}
              />
            </span>
            <span className="num text-right text-label text-muted">{num(r.logloss, 3)}</span>
          </li>
        )
      })}
      <li className="grid grid-cols-[minmax(0,190px)_minmax(0,1fr)_56px] gap-4 px-2 pt-2 text-caption text-muted">
        <span />
        <span className="flex justify-between"><span>← acierta más</span><span>log-loss</span></span>
        <span />
      </li>
    </ul>
  )
}

function Bets({ e }: { e: ModelEval }) {
  const rows = [...e.bets].sort((a, b) => b.roi - a.roi)
  const lo = Math.min(-0.3, ...rows.map((r) => r.roi_ci[0]))
  const hi = Math.max(0.05, ...rows.map((r) => r.roi_ci[1]))
  const x = (v: number) => ((v - lo) / (hi - lo)) * 100
  return (
    <Panel>
      <PanelHeader title="Si se apostara con ellos" sub="Retorno por euro apostado donde el modelo se separa del mercado, con su intervalo del 95 %" />
      <ul className="space-y-3 px-5 pb-5">
        {rows.map((r) => (
          <li key={r.model} className="grid grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)_64px] items-center gap-4 text-label">
            <span className="min-w-0">
              <span className="block truncate">{r.model}</span>
              <span className="num block text-caption text-muted">{int(r.bets)} apuestas</span>
            </span>
            <span className="relative h-6">
              <span className="absolute inset-y-0 w-px bg-line-strong" style={{ left: `${x(0)}%` }} />
              <span className="absolute top-1/2 h-1.5 -translate-y-1/2 rounded-full bg-neg/35" style={{ left: `${x(r.roi_ci[0])}%`, width: `${x(r.roi_ci[1]) - x(r.roi_ci[0])}%` }} />
              <span className="absolute top-1/2 size-3 -translate-x-1/2 -translate-y-1/2 rounded-full bg-neg" style={{ left: `${x(r.roi)}%` }} />
            </span>
            <span className="num text-right font-semibold text-neg">{pct(r.roi, 1)}</span>
          </li>
        ))}
      </ul>
      <p className="px-5 pb-5 text-label text-muted">Ninguna estrategia gana dinero de forma fiable: el margen de las casas se come cualquier ventaja pequeña. Sin dinero real, solo análisis.</p>
    </Panel>
  )
}

export default function Model() {
  useCrumbs([{ label: 'Modelo' }])
  const { data: e, error } = useApi<ModelEval>(api.model)
  if (error) return <ErrorState message="No se pudo cargar la evaluación del modelo." hint="Genera el informe con python -m futdata.models y recarga." />
  const total = e?.leagues.find((l) => l.league === null)
  const gap = total ? total.model.logloss - total.market.logloss : 0
  return (
    <>
      <PageHeader
        title="Modelo"
        sub={e && total ? `Evaluación fuera de muestra · ${e.seasons.map(seasonLabel).join(' y ')} · ${int(total.n)} partidos que el modelo nunca vio` : <Skeleton className="h-4 w-80" />}
      />
      {!e || !total ? (
        <Skeleton className="h-[480px] w-full rounded-panel" />
      ) : (
        <Stagger className="flex flex-col gap-6">
          <StaggerItem>
            <section className="grid gap-8 py-2 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.3fr)] lg:items-center">
              <div>
                <h2 className="text-[34px] leading-[38px] font-semibold tracking-[-0.035em] md:text-[44px] md:leading-[48px]">
                  El mercado sigue por delante.
                </h2>
                <p className="mt-4 max-w-[46ch] text-[16px] leading-[1.6] text-muted">
                  El mejor modelo propio, {e.model}, queda a {num(gap, 3)} de log-loss de las cuotas sin margen. Es mucho mejor que repetir las frecuencias de siempre, pero las casas saben algo más que el Elo y el xG.
                </p>
              </div>
              <div className="grid grid-cols-3 gap-3">
                {[
                  { label: 'Mercado', v: total.market.logloss, tone: 'text-accent' },
                  { label: e.model, v: total.model.logloss, tone: 'text-fg' },
                  { label: 'Frecuencias', v: e.ranking.find((r) => r.model === 'Frecuencias')?.logloss ?? null, tone: 'text-muted' },
                ].map((t) => (
                  <div key={t.label} className="min-w-0">
                    <div className={cx('num text-[30px] leading-9 font-semibold tracking-[-0.03em]', t.tone)}>{num(t.v, 3)}</div>
                    <div className="mt-1 truncate text-label text-muted">{t.label}</div>
                  </div>
                ))}
                <p className="col-span-3 text-caption text-muted">Log-loss medio por partido: menos es mejor.</p>
              </div>
            </section>
          </StaggerItem>

          <StaggerItem className="grid grid-cols-1 gap-8 py-2 lg:grid-cols-3">
            {METRICS.map((m) => {
              const a = total.model[m.k]
              const b = total.market[m.k]
              return (
                <section key={m.k}>
                  <div className="text-label font-medium">{m.label}</div>
                  <div className="mt-3 flex items-baseline gap-6">
                    <div>
                      <div className="num text-[28px] leading-8 font-semibold tracking-[-0.03em]">{num(a, 3)}</div>
                      <div className="text-caption text-muted">{e.model}</div>
                    </div>
                    <div>
                      <div className="num text-[28px] leading-8 font-semibold tracking-[-0.03em] text-accent">{num(b, 3)}</div>
                      <div className="text-caption text-muted">Mercado</div>
                    </div>
                  </div>
                  <p className="mt-3 text-caption text-muted">
                    {a > b ? `El mercado gana por ${num(a - b, 3)}.` : `El modelo gana por ${num(b - a, 3)}.`} {m.hint} Menor es mejor.
                  </p>
                </section>
              )
            })}
          </StaggerItem>

          <StaggerItem>
            <Panel>
              <PanelHeader title="Todos los modelos probados" sub="Mismos partidos de test; la barra gris es el intervalo del 95 % de su distancia al mercado" />
              <Ranking e={e} />
            </Panel>
          </StaggerItem>

          <StaggerItem className="grid grid-cols-1 gap-6 xl:grid-cols-2">
            <Panel>
              <PanelHeader
                title="Calibración"
                sub="Si se dice 30 %, ¿pasa el 30 % de las veces? Las tres salidas de cada partido, por tramos"
                aside={<Legend items={[{ label: e.model, color: 'var(--accent)' }, { label: 'Mercado', color: 'var(--text-muted)', dashed: true }]} />}
              />
              <div className="px-5 pb-5">
                <Calibration model={e.calibration.model} market={e.calibration.market} height={360} />
              </div>
            </Panel>
            <Panel className="overflow-x-auto">
              <PanelHeader title="Por liga" sub={`Log-loss de ${e.model} y del mercado en los mismos partidos`} />
              <table className="w-full min-w-[520px] text-label">
                <thead className="border-y border-line text-caption text-muted">
                  <tr>
                    <th className="px-5 py-2.5 text-left font-normal">Liga</th>
                    <th className="px-2 py-2.5 text-right font-normal">Partidos</th>
                    <th className="px-2 py-2.5 text-right font-normal">Modelo</th>
                    <th className="px-2 py-2.5 text-right font-normal">Mercado</th>
                    <th className="px-5 py-2.5 text-left font-normal">Diferencia</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {e.leagues.map((r) => {
                    const d = r.model.logloss - r.market.logloss
                    const all = r.league === null
                    return (
                      <tr key={r.league ?? 'all'} className={cx('h-12', all && 'bg-surface-2/60')}>
                        <td className={cx('px-5', all && 'font-semibold')}>{all ? 'Todas' : LEAGUES[r.league!].name}</td>
                        <td className="num px-2 text-right text-muted">{int(r.n)}</td>
                        <td className={cx('num px-2 text-right', d < 0 ? 'font-semibold' : 'text-muted')}>{num(r.model.logloss, 3)}</td>
                        <td className={cx('num px-2 text-right', d >= 0 ? 'font-semibold text-accent' : 'text-muted')}>{num(r.market.logloss, 3)}</td>
                        <td className="px-5">
                          <div className="flex items-center gap-2">
                            <div className="h-1.5 w-28 overflow-hidden rounded-full bg-surface-3">
                              <motion.div className="h-full rounded-full bg-neg/80" initial={{ width: 0 }} animate={{ width: `${Math.min(1, Math.abs(d) / 0.03) * 100}%` }} transition={{ duration: 0.7, ease }} />
                            </div>
                            <span className="num text-caption text-muted">{d >= 0 ? '+' : '−'}{num(Math.abs(d), 3)}</span>
                          </div>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
              <p className="px-5 py-4 text-caption text-muted">Valores positivos: el mercado está por delante. Mejor valor de cada fila en negrita.</p>
            </Panel>
          </StaggerItem>

          <StaggerItem>{e.bets.length > 0 && <Bets e={e} />}</StaggerItem>
        </Stagger>
      )}
    </>
  )
}
