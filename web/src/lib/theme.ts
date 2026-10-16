import { useCallback, useSyncExternalStore } from 'react'

export type Theme = 'dark' | 'light'
const KEY = 'halfline.theme'
const listeners = new Set<() => void>()

function read(): Theme {
  try {
    return (localStorage.getItem(KEY) as Theme) || 'dark'
  } catch {
    return 'dark'
  }
}

export function applyTheme(theme: Theme = read()) {
  document.documentElement.dataset.theme = theme
}

type ClickLike = { clientX: number; clientY: number }

export function useTheme(): [Theme, (from?: ClickLike) => void] {
  const theme = useSyncExternalStore(
    (cb) => (listeners.add(cb), () => listeners.delete(cb)),
    read,
  )
  const toggle = useCallback((from?: ClickLike) => {
    const next: Theme = read() === 'dark' ? 'light' : 'dark'
    try {
      localStorage.setItem(KEY, next)
    } catch {
      /* sin almacenamiento: el cambio dura hasta recargar */
    }
    const swap = () => {
      applyTheme(next)
      listeners.forEach((l) => l())
    }
    // El tema nuevo se abre en círculo desde donde se pulsó (View Transitions, si el navegador las tiene)
    type VT = { ready: Promise<void>; finished: Promise<void> }
    const doc = document as Document & { startViewTransition?: (cb: () => void) => VT }
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    if (!doc.startViewTransition || reduce || document.visibilityState !== 'visible') return swap()
    const root = document.documentElement
    root.style.setProperty('--vt-x', `${from?.clientX ?? window.innerWidth - 40}px`)
    root.style.setProperty('--vt-y', `${from?.clientY ?? 24}px`)
    const vt = doc.startViewTransition(swap)
    // Si el navegador aborta la animación, el tema ya está cambiado: no hay nada más que hacer
    vt.ready.catch(() => {})
    vt.finished.catch(() => {})
  }, [])
  return [theme, toggle]
}
