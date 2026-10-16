import { lazy, Suspense } from 'react'
import { motion } from 'motion/react'
import { BrowserRouter, Outlet, Route, Routes, useLocation } from 'react-router-dom'
import { AppShell, useCrumbs } from './components/shell'
import { ErrorState, Skeleton } from './components/ui'
import { api, useApi, type Meta } from './lib/api'
import Today from './pages/Today'

const Matches = lazy(() => import('./pages/Matches'))
const Match = lazy(() => import('./pages/Match'))
const League = lazy(() => import('./pages/League'))
const Team = lazy(() => import('./pages/Team'))
const Model = lazy(() => import('./pages/Model'))
const Data = lazy(() => import('./pages/Data'))
const Landing = lazy(() => import('./pages/Landing'))
const StylesPage = lazy(() => import('./pages/Styles'))
const Players = lazy(() => import('./pages/Players'))

function NotFound() {
  useCrumbs([{ label: 'No encontrado' }])
  return <ErrorState message="Esta página no existe." hint="Usa ⌘K para buscar un equipo, un partido o una liga." />
}

/** Las páginas necesitan /api/meta (nombres completos y escudos) antes de pintarse. */
function MetaGate({ children }: { children: React.ReactNode }) {
  const { data, error } = useApi<Meta>(api.meta)
  if (error) return <ErrorState message="No se pudo conectar con la API de datos." />
  if (!data) return <Skeleton className="h-96 w-full" />
  return <>{children}</>
}

/** Aparición breve al cambiar de página (solo opacidad y 4px de desplazamiento). */
function PageFade({ children }: { children: React.ReactNode }) {
  const { pathname } = useLocation()
  return (
    <motion.div key={pathname} initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.22, ease: [0.16, 1, 0.3, 1] }}>
      {children}
    </motion.div>
  )
}

function AppLayout() {
  return (
    <AppShell>
      <MetaGate>
        <Suspense fallback={<Skeleton className="h-96 w-full" />}>
          <PageFade>
            <Outlet />
          </PageFade>
        </Suspense>
      </MetaGate>
    </AppShell>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route
          path="/"
          element={
            <MetaGate>
              <Suspense fallback={null}>
                <Landing />
              </Suspense>
            </MetaGate>
          }
        />
        <Route element={<AppLayout />}>
          <Route path="/hoy" element={<Today />} />
          <Route path="/partidos" element={<Matches />} />
          <Route path="/partidos/:id" element={<Match />} />
          <Route path="/ligas/:league" element={<League />} />
          <Route path="/equipos/:league/:team" element={<Team />} />
          <Route path="/estilos" element={<StylesPage />} />
          <Route path="/jugadores" element={<Players />} />
          <Route path="/modelo" element={<Model />} />
          <Route path="/datos" element={<Data />} />
          <Route path="*" element={<NotFound />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
