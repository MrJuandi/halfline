import { AnimatePresence, motion } from 'motion/react'
import {
  CalendarDays,
  ChevronRight,
  Database,
  FlaskConical,
  ListOrdered,
  Moon,
  Orbit,
  UserRound,
  PanelLeft,
  Search,
  Sun,
  Trophy,
} from 'lucide-react'
import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import { Link, NavLink, useLocation } from 'react-router-dom'
import { api, useApi, type Meta } from '../lib/api'
import { LEAGUE_ORDER, LEAGUES, date } from '../lib/format'
import { useTheme } from '../lib/theme'
import { CommandMenu } from './command'
import { cx, Kbd, Logo } from './ui'

/* ---------------------------------------------------------------- migas de pan */

export type Crumb = { label: string; to?: string }
const CrumbCtx = createContext<(c: Crumb[]) => void>(() => {})

/** Cada página declara sus migas de pan. */
export function useCrumbs(crumbs: Crumb[]) {
  const set = useContext(CrumbCtx)
  const key = JSON.stringify(crumbs)
  useEffect(() => {
    set(JSON.parse(key))
    document.title = [...JSON.parse(key)].reverse().map((c: Crumb) => c.label).concat('Halfline').join(' · ')
  }, [key, set])
}

/* ---------------------------------------------------------------- barra lateral */

function NavItem({ to, icon, label, collapsed, end }: { to: string; icon: ReactNode; label: string; collapsed: boolean; end?: boolean }) {
  return (
    <NavLink
      to={to}
      end={end}
      title={collapsed ? label : undefined}
      className={({ isActive }) =>
        cx(
          'group relative flex h-8 items-center gap-2.5 rounded-ctl px-2 text-label font-medium transition-[color,background-color,transform] duration-[120ms] active:scale-[0.98]',
          isActive ? 'text-fg' : 'text-muted hover:bg-surface-2 hover:text-fg',
        )
      }
    >
      {({ isActive }) => (
        <>
          {/* Un solo indicador que se desliza entre secciones en vez de aparecer y desaparecer */}
          {isActive && (
            <motion.span
              layoutId="nav-active"
              className="absolute inset-0 rounded-ctl bg-surface-3"
              transition={{ type: 'spring', bounce: 0.12, duration: 0.38 }}
            >
              <span className="absolute top-1.5 bottom-1.5 left-0 w-[2px] rounded-full bg-accent" />
            </motion.span>
          )}
          <span className="relative grid size-4 shrink-0 place-items-center">{icon}</span>
          {!collapsed && <span className="relative truncate">{label}</span>}
        </>
      )}
    </NavLink>
  )
}

function Sidebar({ collapsed, onToggle }: { collapsed: boolean; onToggle: () => void }) {
  const { data: meta } = useApi<Meta>(api.meta)
  const season = meta?.leagues[0]?.seasons.at(-1)
  return (
    <aside
      className={cx(
        'sticky top-0 hidden h-dvh shrink-0 flex-col border-r border-line bg-surface-1 transition-[width] duration-200 ease-[var(--ease-out)] md:flex',
        collapsed ? 'w-14' : 'w-[232px]',
      )}
    >
      <div className={cx('flex h-12 items-center gap-2.5 border-b border-line', collapsed ? 'justify-center' : 'px-4')}>
        <Link to="/" className="flex items-center gap-2.5" aria-label="Halfline, inicio">
          <Logo />
          {!collapsed && <span className="text-[15px] font-semibold tracking-[-0.01em]">Halfline</span>}
        </Link>
      </div>

      <nav className="flex flex-1 flex-col gap-0.5 overflow-y-auto p-2">
        <NavItem to="/hoy" icon={<CalendarDays size={16} strokeWidth={1.6} />} label="Hoy" collapsed={collapsed} />
        <NavItem to="/partidos" icon={<ListOrdered size={16} strokeWidth={1.6} />} label="Partidos" collapsed={collapsed} />
        <NavItem to="/estilos" icon={<Orbit size={16} strokeWidth={1.6} />} label="Estilos" collapsed={collapsed} />
        <NavItem to="/jugadores" icon={<UserRound size={16} strokeWidth={1.6} />} label="Jugadores" collapsed={collapsed} />
        <NavItem to="/modelo" icon={<FlaskConical size={16} strokeWidth={1.6} />} label="Modelo" collapsed={collapsed} />

        <div className={cx('mt-5 mb-1 px-2 text-caption text-subtle', collapsed && 'sr-only')}>Ligas</div>
        {collapsed && <div className="mx-auto my-2 h-px w-6 bg-line" />}
        {LEAGUE_ORDER.map((code) => (
          <NavItem
            key={code}
            to={`/ligas/${code}${season ? `?temporada=${season}` : ''}`}
            icon={
              collapsed ? (
                <span className="text-[9px] font-semibold text-subtle">{LEAGUES[code].short}</span>
              ) : (
                <Trophy size={15} strokeWidth={1.6} className="text-subtle" />
              )
            }
            label={LEAGUES[code].name}
            collapsed={collapsed}
          />
        ))}

        <div className="mt-auto pt-4">
          <NavItem to="/datos" icon={<Database size={16} strokeWidth={1.6} />} label="Datos" collapsed={collapsed} />
        </div>
      </nav>

      <div className={cx('flex items-center border-t border-line p-2', collapsed ? 'justify-center' : 'justify-between')}>
        {!collapsed && meta && (
          <span className="px-2 text-caption text-subtle">Datos hasta {date(meta.data_through)}</span>
        )}
        <button
          onClick={onToggle}
          className="grid size-7 place-items-center rounded-ctl text-subtle transition-colors hover:bg-surface-2 hover:text-fg"
          title="Plegar barra lateral ( [ )"
          aria-label="Plegar barra lateral"
        >
          <PanelLeft size={15} strokeWidth={1.6} />
        </button>
      </div>
    </aside>
  )
}

/* ---------------------------------------------------------------- barra superior */

function Topbar({ crumbs, onSearch }: { crumbs: Crumb[]; onSearch: () => void }) {
  const [theme, toggle] = useTheme()
  return (
    <header className="sticky top-0 z-20 flex h-12 items-center gap-3 border-b border-line bg-[color-mix(in_srgb,var(--bg)_88%,transparent)] px-4 backdrop-blur-md md:px-6">
      <Link to="/" className="md:hidden" aria-label="Inicio">
        <Logo />
      </Link>
      <nav aria-label="Migas de pan" className="flex min-w-0 items-center gap-1.5 text-label">
        {crumbs.map((c, i) => (
          <span key={i} className="flex min-w-0 items-center gap-1.5">
            {i > 0 && <ChevronRight size={13} className="shrink-0 text-subtle" />}
            {c.to && i < crumbs.length - 1 ? (
              <Link to={c.to} className="truncate text-muted transition-colors hover:text-fg">
                {c.label}
              </Link>
            ) : (
              <span className="truncate font-medium text-fg">{c.label}</span>
            )}
          </span>
        ))}
      </nav>
      <div className="ml-auto flex items-center gap-2">
        <button
          onClick={onSearch}
          className="flex h-9 items-center gap-2 rounded-ctl bg-surface-1 pl-3 pr-1.5 text-label text-muted transition-[color,background-color,transform] hover:bg-surface-3 hover:text-fg active:scale-[0.98]"
        >
          <Search size={14} strokeWidth={1.7} />
          <span className="hidden w-40 text-left sm:block">Buscar equipo o partido</span>
          <span className="hidden gap-0.5 sm:flex">
            <Kbd>⌘</Kbd>
            <Kbd>K</Kbd>
          </span>
        </button>
        <button
          onClick={(e) => toggle(e)}
          className="grid size-8 place-items-center rounded-ctl text-subtle transition-[color,background-color,transform] hover:bg-surface-2 hover:text-fg active:scale-90"
          aria-label={theme === 'dark' ? 'Cambiar a modo claro' : 'Cambiar a modo oscuro'}
          title={theme === 'dark' ? 'Modo claro' : 'Modo oscuro'}
        >
          <AnimatePresence mode="wait" initial={false}>
            <motion.span
              key={theme}
              initial={{ opacity: 0, rotate: -30, scale: 0.8 }}
              animate={{ opacity: 1, rotate: 0, scale: 1 }}
              exit={{ opacity: 0, rotate: 30, scale: 0.8 }}
              transition={{ duration: 0.15 }}
              className="grid place-items-center"
            >
              {theme === 'dark' ? <Sun size={15} strokeWidth={1.6} /> : <Moon size={15} strokeWidth={1.6} />}
            </motion.span>
          </AnimatePresence>
        </button>
      </div>
    </header>
  )
}

/* ---------------------------------------------------------------- navegación móvil */

function MobileNav() {
  const items = [
    { to: '/hoy', label: 'Hoy', icon: <CalendarDays size={18} strokeWidth={1.6} />, end: true },
    { to: '/partidos', label: 'Partidos', icon: <ListOrdered size={18} strokeWidth={1.6} /> },
    { to: '/ligas/SP1', label: 'Ligas', icon: <Trophy size={18} strokeWidth={1.6} /> },
    { to: '/modelo', label: 'Modelo', icon: <FlaskConical size={18} strokeWidth={1.6} /> },
  ]
  return (
    <nav className="fixed inset-x-0 bottom-0 z-30 grid grid-cols-4 border-t border-line bg-surface-1 pb-[env(safe-area-inset-bottom)] md:hidden">
      {items.map((i) => (
        <NavLink
          key={i.to}
          to={i.to}
          end={i.end}
          className={({ isActive }) => cx('relative flex h-14 flex-col items-center justify-center gap-1 text-micro transition-colors active:scale-95', isActive ? 'text-fg' : 'text-subtle')}
        >
          {({ isActive }) => (
            <>
              {isActive && <motion.span layoutId="mnav-active" className="absolute top-0 h-[2px] w-8 rounded-full bg-accent" transition={{ type: 'spring', bounce: 0.15, duration: 0.4 }} />}
              {i.icon}
              {i.label}
            </>
          )}
        </NavLink>
      ))}
    </nav>
  )
}

/* ---------------------------------------------------------------- armazón */

export function AppShell({ children }: { children: ReactNode }) {
  const [crumbs, setCrumbs] = useState<Crumb[]>([])
  const [collapsed, setCollapsed] = useState(() => {
    try {
      return localStorage.getItem('halfline.sidebar') === '1'
    } catch {
      return false
    }
  })
  const [searchOpen, setSearchOpen] = useState(false)
  const location = useLocation()

  useEffect(() => {
    try {
      localStorage.setItem('halfline.sidebar', collapsed ? '1' : '0')
    } catch {
      /* preferencia no persistida */
    }
  }, [collapsed])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const typing = (e.target as HTMLElement)?.closest('input, textarea, [contenteditable]')
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        setSearchOpen((o) => !o)
      } else if (!typing && e.key === '/') {
        e.preventDefault()
        setSearchOpen(true)
      } else if (!typing && e.key === '[') {
        setCollapsed((c) => !c)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  useEffect(() => {
    window.scrollTo({ top: 0 }) // en Chrome reciente devuelve una promesa: no puede ser el valor de retorno del efecto
  }, [location.pathname])

  return (
    <CrumbCtx.Provider value={setCrumbs}>
      <div className="flex min-h-dvh">
        <Sidebar collapsed={collapsed} onToggle={() => setCollapsed((c) => !c)} />
        <div className="relative flex min-w-0 flex-1 flex-col">
          <Topbar crumbs={crumbs} onSearch={() => setSearchOpen(true)} />
          <main className="relative isolate w-full max-w-[1320px] flex-1 px-4 pt-6 pb-24 md:px-8 md:pt-8 md:pb-16">{children}</main>
        </div>
      </div>
      <MobileNav />
      <CommandMenu open={searchOpen} onOpenChange={setSearchOpen} />
    </CrumbCtx.Provider>
  )
}

/** Cabecera de página: un único título y, opcionalmente, una línea de contexto y acciones. */
export function PageHeader({ title, sub, actions }: { title: ReactNode; sub?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0">
        <h1 className="mask-line text-display font-semibold">
          <motion.span className="block" initial={{ y: '100%' }} animate={{ y: 0 }} transition={{ duration: 0.55, ease: [0.16, 1, 0.3, 1] }}>
            {title}
          </motion.span>
        </h1>
        {sub && (
          <motion.div className="mt-1.5 text-body text-muted" initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.4, delay: 0.12 }}>
            {sub}
          </motion.div>
        )}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  )
}
