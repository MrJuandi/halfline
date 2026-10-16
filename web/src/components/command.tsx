import { Command } from 'cmdk'
import { AnimatePresence, motion } from 'motion/react'
import { CalendarDays, CornerDownLeft, Database, FlaskConical, ListOrdered, Moon, Shield, Trophy } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, useApi, type MatchSummary, type Meta, type TeamRef, teamName as tn } from '../lib/api'
import { LEAGUE_ORDER, LEAGUES, day } from '../lib/format'
import { useTheme } from '../lib/theme'
import { Kbd, TeamBadge } from './ui'

const itemClass =
  'flex h-9 cursor-default items-center gap-2.5 rounded-ctl px-2.5 text-label text-muted data-[selected=true]:bg-surface-3 data-[selected=true]:text-fg'
const groupClass =
  '[&_[cmdk-group-heading]]:px-2.5 [&_[cmdk-group-heading]]:pt-3 [&_[cmdk-group-heading]]:pb-1.5 [&_[cmdk-group-heading]]:text-caption [&_[cmdk-group-heading]]:text-subtle'

export function CommandMenu({ open, onOpenChange }: { open: boolean; onOpenChange: (o: boolean) => void }) {
  const navigate = useNavigate()
  const [, toggleTheme] = useTheme()
  const [query, setQuery] = useState('')
  const { data: teams } = useApi<TeamRef[]>(open ? api.teams : null)
  const { data: meta } = useApi<Meta>(api.meta)
  const season = meta?.leagues[0]?.seasons.at(-1)
  const { data: recent } = useApi<MatchSummary[]>(open && season ? api.matches({ season, limit: 400 }) : null)

  useEffect(() => {
    if (!open) setQuery('')
  }, [open])

  const go = (to: string) => {
    onOpenChange(false)
    navigate(to)
  }

  // Equipos de la temporada actual primero; el resto, solo al escribir.
  const teamItems = useMemo(() => {
    if (!teams) return []
    const current = teams.filter((t) => season && t.seasons.includes(season))
    return query ? teams : current
  }, [teams, season, query])

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          className="fixed inset-0 z-50 flex items-start justify-center bg-black/50 px-4 pt-[14vh]"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0, transition: { duration: 0.12 } }}
          transition={{ duration: 0.15 }}
          onMouseDown={() => onOpenChange(false)}
        >
          <motion.div
            onMouseDown={(e) => e.stopPropagation()}
            initial={{ opacity: 0, scale: 0.97, y: -6 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.98, transition: { duration: 0.12, ease: [0.4, 0, 1, 1] } }}
            transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
            className="w-full max-w-[600px] overflow-hidden rounded-dialog border border-line-strong bg-surface-2 float-shadow"
          >
            <Command
              label="Buscar"
              loop
              onKeyDown={(e) => e.key === 'Escape' && onOpenChange(false)}
              filter={(value, search, keywords) => {
                const hay = `${value} ${(keywords ?? []).join(' ')}`.toLowerCase().normalize('NFD').replace(/\p{Diacritic}/gu, '')
                const terms = search.toLowerCase().normalize('NFD').replace(/\p{Diacritic}/gu, '').split(/\s+/).filter(Boolean)
                return terms.every((t) => hay.includes(t)) ? 1 : 0
              }}
            >
              <div className="flex items-center gap-2 border-b border-line px-4">
                <Command.Input
                  autoFocus
                  value={query}
                  onValueChange={setQuery}
                  placeholder="Busca un equipo, un partido («bar rma») o una página"
                  className="h-12 flex-1 bg-transparent text-[15px] text-fg outline-none placeholder:text-subtle"
                />
                <Kbd>esc</Kbd>
              </div>
              <Command.List className="max-h-[380px] overflow-y-auto p-1.5">
                <Command.Empty className="px-3 py-8 text-center text-muted">Sin resultados para «{query}».</Command.Empty>

                <Command.Group heading="Ir a" className={groupClass}>
                  {[
                    { to: '/', label: 'Portada', icon: <CalendarDays size={15} /> },
                    { to: '/hoy', label: 'Hoy', icon: <CalendarDays size={15} /> },
                    { to: '/partidos', label: 'Partidos', icon: <ListOrdered size={15} /> },
                    { to: '/estilos', label: 'Estilos de juego', icon: <FlaskConical size={15} /> },
                    { to: '/jugadores', label: 'Jugadores', icon: <FlaskConical size={15} /> },
                    { to: '/modelo', label: 'Modelo', icon: <FlaskConical size={15} /> },
                    { to: '/datos', label: 'Datos', icon: <Database size={15} /> },
                  ].map((p) => (
                    <Command.Item key={p.to} value={`página ${p.label}`} onSelect={() => go(p.to)} className={itemClass}>
                      <span className="text-subtle">{p.icon}</span>
                      {p.label}
                    </Command.Item>
                  ))}
                  {LEAGUE_ORDER.map((code) => (
                    <Command.Item
                      key={code}
                      value={`liga ${LEAGUES[code].name}`}
                      keywords={[LEAGUES[code].country]}
                      onSelect={() => go(`/ligas/${code}`)}
                      className={itemClass}
                    >
                      <Trophy size={15} className="text-subtle" />
                      {LEAGUES[code].name}
                      <span className="ml-auto text-caption text-subtle">Clasificación</span>
                    </Command.Item>
                  ))}
                </Command.Group>

                {teamItems.length > 0 && (
                  <Command.Group heading="Equipos" className={groupClass}>
                    {teamItems.map((t) => (
                      <Command.Item
                        key={`${t.league}-${t.team}`}
                        value={`equipo ${t.team} ${tn(t.team)} ${t.league}`}
                        keywords={[LEAGUES[t.league].name]}
                        onSelect={() => go(`/equipos/${t.league}/${encodeURIComponent(t.team)}`)}
                        className={itemClass}
                      >
                        <TeamBadge team={t.team} size={18} />
                        {tn(t.team)}
                        <span className="ml-auto text-caption text-subtle">{LEAGUES[t.league].name}</span>
                      </Command.Item>
                    ))}
                  </Command.Group>
                )}

                {query.length >= 2 && recent && (
                  <Command.Group heading="Partidos de esta temporada" className={groupClass}>
                    {recent.map((m) => (
                      <Command.Item
                        key={m.match_id}
                        value={`partido ${tn(m.home)} ${tn(m.away)} ${m.home} ${m.away} ${m.match_id}`}
                        onSelect={() => go(`/partidos/${m.match_id}`)}
                        className={itemClass}
                      >
                        <Shield size={15} className="text-subtle" />
                        <span className="truncate">
                          {tn(m.home)} <span className="num text-fg">{m.home_goals}–{m.away_goals}</span> {tn(m.away)}
                        </span>
                        <span className="ml-auto shrink-0 text-caption text-subtle">{day(m.kickoff)}</span>
                      </Command.Item>
                    ))}
                  </Command.Group>
                )}

                <Command.Group heading="Acciones" className={groupClass}>
                  <Command.Item
                    value="acción cambiar tema modo claro oscuro"
                    onSelect={() => {
                      toggleTheme()
                      onOpenChange(false)
                    }}
                    className={itemClass}
                  >
                    <Moon size={15} className="text-subtle" />
                    Cambiar entre modo claro y oscuro
                  </Command.Item>
                </Command.Group>
              </Command.List>
              <div className="flex items-center gap-4 border-t border-line px-4 py-2 text-caption text-subtle">
                <span className="flex items-center gap-1.5">
                  <Kbd>↑</Kbd>
                  <Kbd>↓</Kbd> moverse
                </span>
                <span className="flex items-center gap-1.5">
                  <Kbd>
                    <CornerDownLeft size={11} />
                  </Kbd>
                  abrir
                </span>
              </div>
            </Command>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
