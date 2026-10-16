import { motion } from 'motion/react'
import { ChevronDown } from 'lucide-react'
import { useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { useTeams, type Outcome, type Probs } from '../lib/api'
import { initials, pct, pp } from '../lib/format'

export const cx = (...c: (string | false | null | undefined)[]) => c.filter(Boolean).join(' ')

/* ---------------------------------------------------------------- marca */

export function Logo({ size = 18 }: { size?: number }) {
  // Círculo central cortado por la línea de medio campo (acento): el punto justo entre local y visitante.
  return (
    <svg width={size} height={size} viewBox="0 0 18 18" aria-hidden>
      <circle cx="9" cy="9" r="5.5" fill="none" stroke="var(--text-subtle)" strokeWidth="1.6" />
      <path d="M9 1.5 V16.5" stroke="var(--accent)" strokeWidth="2.2" strokeLinecap="round" />
    </svg>
  )
}

/* ---------------------------------------------------------------- equipos */

export function TeamBadge({ team, size = 20 }: { team: string; size?: number }) {
  const { crest } = useTeams()
  const src = crest(team)
  const [failed, setFailed] = useState(false)
  if (src && !failed)
    return (
      <img
        src={src}
        alt=""
        aria-hidden
        loading="lazy"
        onError={() => setFailed(true)}
        className="shrink-0 object-contain"
        style={{ width: size, height: size }}
      />
    )
  return (
    <span
      aria-hidden
      className="inline-grid shrink-0 place-items-center rounded-[5px] bg-surface-3 font-medium text-muted hairline"
      style={{ width: size, height: size, fontSize: Math.max(7, size * 0.36), letterSpacing: '-0.02em' }}
    >
      {initials(team)}
    </span>
  )
}

/** Nombre completo del equipo (el canónico se usa solo en URLs y datos). */
export function TeamName({ team }: { team: string }) {
  const { name } = useTeams()
  return <>{name(team)}</>
}

export function TeamLink({ league, team, className }: { league: string; team: string; className?: string }) {
  return (
    <Link
      to={`/equipos/${league}/${encodeURIComponent(team)}`}
      onClick={(e) => e.stopPropagation()}
      className={cx('rounded-sm decoration-line-strong underline-offset-4 hover:underline', className)}
    >
      <TeamName team={team} />
    </Link>
  )
}

/* ---------------------------------------------------------------- forma */

const FORM_STYLE: Record<Outcome, string> = {
  W: 'bg-accent-soft text-accent',
  D: 'bg-surface-3 text-muted',
  L: 'bg-[color-mix(in_srgb,var(--neg)_14%,transparent)] text-neg',
}
const FORM_LABEL: Record<Outcome, string> = { W: 'V', D: 'E', L: 'D' }

export function FormSquares({ form, size = 16 }: { form: Outcome[]; size?: number }) {
  return (
    <span className="inline-flex gap-[3px]" aria-label={`Forma: ${form.map((f) => FORM_LABEL[f]).join(' ')}`}>
      {form.map((f, i) => (
        <span
          key={i}
          className={cx('grid place-items-center rounded-[3px] font-medium', FORM_STYLE[f])}
          style={{ width: size, height: size, fontSize: size * 0.6 }}
        >
          {FORM_LABEL[f]}
        </span>
      ))}
    </span>
  )
}

/* ---------------------------------------------------------------- barra 1X2 */

/** Barra apilada local · empate · visitante. `dashed` = mercado (codificación fija). */
export function ProbBar({
  probs,
  height = 6,
  labels = false,
  muted = false,
}: {
  probs: Probs
  height?: number
  labels?: boolean
  muted?: boolean
}) {
  const parts = [
    { k: 'home', v: probs.home, c: 'var(--home)' },
    { k: 'draw', v: probs.draw, c: 'var(--draw)' },
    { k: 'away', v: probs.away, c: 'var(--away)' },
  ]
  return (
    <div className="flex w-full gap-[2px]" style={{ height }}>
      {parts.map((p) => (
        <motion.div
          key={p.k}
          className="relative h-full overflow-hidden first:rounded-l-[3px] last:rounded-r-[3px]"
          initial={false}
          animate={{ flexGrow: Math.max(p.v, 0.001) }}
          transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
          style={{ flexBasis: 0, background: p.c, opacity: muted ? 0.38 : 1 }}
        >
          {labels && p.v >= 0.12 && (
            <span className="absolute inset-0 grid place-items-center text-[11px] font-medium text-bg">
              {pct(p.v)}
            </span>
          )}
        </motion.div>
      ))}
    </div>
  )
}

/** Tres cifras 1 · X · 2 alineadas, en sus colores. */
export function ProbTriplet({ probs, className }: { probs: Probs; className?: string }) {
  return (
    <span className={cx('num inline-flex gap-3 text-label', className)}>
      <span className="text-home">{pct(probs.home)}</span>
      <span className="text-draw">{pct(probs.draw)}</span>
      <span className="text-away">{pct(probs.away)}</span>
    </span>
  )
}

export function Delta({ value, threshold = 0.03 }: { value: number; threshold?: number }) {
  const strong = Math.abs(value) >= threshold
  return (
    <span className={cx('num text-label', strong ? (value > 0 ? 'text-pos' : 'text-neg') : 'text-subtle')}>
      {pp(value)}
    </span>
  )
}

/* ---------------------------------------------------------------- piezas sueltas */

export function Kbd({ children }: { children: ReactNode }) {
  return (
    <kbd className="inline-grid h-[18px] min-w-[18px] place-items-center rounded-[4px] border border-line bg-surface-2 px-1 font-sans text-[11px] font-medium text-muted">
      {children}
    </kbd>
  )
}

export function Badge({ children, tone = 'neutral' }: { children: ReactNode; tone?: 'neutral' | 'accent' | 'warn' }) {
  const tones = {
    neutral: 'bg-surface-3 text-muted',
    accent: 'bg-accent-soft text-accent',
    warn: 'bg-away-soft text-away',
  }
  return (
    <span className={cx('inline-flex h-5 shrink-0 items-center whitespace-nowrap rounded-[4px] px-1.5 text-micro font-medium', tones[tone])}>
      {children}
    </span>
  )
}

export function Skeleton({ className, style }: { className?: string; style?: React.CSSProperties }) {
  return <div className={cx('skeleton', className)} style={style} />
}

/** Superficie: un paso de tono sobre el fondo, sin borde ni sombra (como la portada). */
export function Panel({ children, className }: { children: ReactNode; className?: string }) {
  return <section className={cx('rounded-panel bg-surface-1', className)}>{children}</section>
}

export function PanelHeader({ title, aside, sub }: { title: ReactNode; aside?: ReactNode; sub?: ReactNode }) {
  return (
    <header className="flex min-h-12 items-start justify-between gap-4 px-5 pt-4 pb-3">
      <div className="min-w-0">
        <h3 className="text-[16px] leading-6 font-semibold tracking-[-0.01em]">{title}</h3>
        {sub && <p className="mt-0.5 text-label text-muted">{sub}</p>}
      </div>
      {aside && <div className="flex shrink-0 items-center gap-2">{aside}</div>}
    </header>
  )
}

export function ErrorState({ message, hint }: { message: string; hint?: string }) {
  return (
    <div className="rounded-panel bg-surface-1 px-6 py-10">
      <p className="text-[18px] font-semibold tracking-[-0.01em]">{message}</p>
      <p className="mt-1 max-w-prose text-muted">
        {hint ?? 'Comprueba que la API de datos está en marcha con python -m futdata.api y recarga la página.'}
      </p>
    </div>
  )
}

/** Control segmentado (p. ej. temporada, ventana). El indicador se desliza con layoutId. */
export function Segmented<T extends string | number>({
  value,
  options,
  onChange,
  id,
}: {
  value: T
  options: { value: T; label: ReactNode }[]
  onChange: (v: T) => void
  id: string
}) {
  return (
    <div role="radiogroup" className="inline-flex h-9 items-center rounded-ctl bg-surface-1 p-1">
      {options.map((o) => {
        const active = o.value === value
        return (
          <button
            key={String(o.value)}
            role="radio"
            aria-checked={active}
            onClick={() => onChange(o.value)}
            className={cx(
              'relative h-full rounded-[6px] px-3 text-label font-medium transition-[color,transform] duration-[120ms] active:scale-[0.96]',
              active ? 'text-fg' : 'text-muted hover:text-fg',
            )}
          >
            {active && (
              <motion.span
                layoutId={`seg-${id}`}
                className="absolute inset-0 rounded-[6px] bg-surface-3"
                transition={{ type: 'spring', bounce: 0, duration: 0.3 }}
              />
            )}
            <span className="relative">{o.label}</span>
          </button>
        )
      })}
    </div>
  )
}

/** Pestañas subrayadas sincronizadas con la URL por quien las usa. */
export function Tabs<T extends string>({
  value,
  tabs,
  onChange,
  id,
}: {
  value: T
  tabs: { value: T; label: string; disabled?: boolean; hint?: string }[]
  onChange: (v: T) => void
  id: string
}) {
  return (
    <div role="tablist" className="flex gap-1 border-b border-line">
      {tabs.map((t) => {
        const active = t.value === value
        return (
          <button
            key={t.value}
            role="tab"
            aria-selected={active}
            disabled={t.disabled}
            title={t.hint}
            onClick={() => onChange(t.value)}
            className={cx(
              'relative -mb-px h-11 px-3.5 text-[14px] font-medium transition-colors duration-[120ms]',
              active ? 'text-fg' : 'text-muted hover:text-fg',
              t.disabled && 'opacity-40',
            )}
          >
            {t.label}
            {active && (
              <motion.span
                layoutId={`tab-${id}`}
                className="absolute inset-x-2.5 -bottom-px h-[2px] rounded-full bg-accent"
                transition={{ type: 'spring', bounce: 0, duration: 0.32 }}
              />
            )}
          </button>
        )
      })}
    </div>
  )
}

/** Desplegable nativo con el aspecto de los demás controles. */
export function Select<T extends string | number>({
  value,
  options,
  onChange,
  label,
}: {
  value: T | undefined
  options: { value: T; label: string }[]
  onChange: (v: string) => void
  label: string
}) {
  return (
    <label className="relative inline-flex h-9 items-center rounded-ctl bg-surface-1 text-label font-medium transition-colors hover:bg-surface-3 focus-within:outline-2 focus-within:outline-accent">
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        aria-label={label}
        className="h-full appearance-none bg-transparent pr-8 pl-3 text-fg outline-none"
      >
        {options.map((o) => (
          <option key={String(o.value)} value={o.value}>{o.label}</option>
        ))}
      </select>
      <ChevronDown size={14} className="pointer-events-none absolute right-2.5 text-muted" />
    </label>
  )
}

/** Cifra destacada: etiqueta pequeña, número grande, nota debajo. */
export function Stat({ label, value, sub, tone }: { label: ReactNode; value: ReactNode; sub?: ReactNode; tone?: 'pos' | 'neg' | 'accent' }) {
  return (
    <div className="min-w-0 rounded-panel bg-surface-1 px-5 py-4">
      <div className="text-label text-muted">{label}</div>
      <div
        className={cx(
          'num mt-1.5 truncate text-[28px] leading-8 font-semibold tracking-[-0.03em]',
          tone === 'pos' && 'text-pos',
          tone === 'neg' && 'text-neg',
          tone === 'accent' && 'text-accent',
        )}
      >
        {value}
      </div>
      {sub && <div className="mt-1 line-clamp-2 text-caption text-muted tnum">{sub}</div>}
    </div>
  )
}

/** Entrada escalonada para los bloques de una página: cada hijo sube 12 px con 60 ms de retraso. */
export function Stagger({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <motion.div
      className={className}
      initial="hidden"
      animate="show"
      variants={{ hidden: {}, show: { transition: { staggerChildren: 0.06, delayChildren: 0.05 } } }}
    >
      {children}
    </motion.div>
  )
}

export function StaggerItem({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <motion.div
      className={className}
      variants={{ hidden: { opacity: 0, y: 12 }, show: { opacity: 1, y: 0, transition: { duration: 0.45, ease: [0.16, 1, 0.3, 1] } } }}
    >
      {children}
    </motion.div>
  )
}
