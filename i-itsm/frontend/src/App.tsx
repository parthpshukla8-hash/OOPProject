import { FluentProvider, Spinner } from '@fluentui/react-components'
import { useEffect, useState } from 'react'
import type { ReactElement } from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import type { UserRole } from './api/types'
import { AppShell } from './components/AppShell'
import { AuthProvider } from './features/auth/AuthProvider'
import { useAuth } from './features/auth/auth-context'
import { AdministrationPage } from './pages/AdministrationPage'
import { AuditLogPage } from './pages/AuditLogPage'
import { IncidentWorkspacePage } from './pages/IncidentWorkspacePage'
import { LoginPage } from './pages/LoginPage'
import { ReportIncidentPage } from './pages/ReportIncidentPage'
import { ReportsPage } from './pages/ReportsPage'
import { ServiceMapPage } from './pages/ServiceMapPage'
import { SituationPage } from './pages/SituationPage'
import { darkTheme, lightTheme } from './theme/theme'

const THEME_STORAGE_KEY = 'iitsm.theme'
type ThemeMode = 'light' | 'dark'

function RequireRole({ roles, children }: { roles: UserRole[]; children: ReactElement }) {
  const { user } = useAuth()
  return user && roles.includes(user.role) ? children : <Navigate to="/incidents" replace />
}

function AppRoutes({ themeMode, onToggleTheme }: { themeMode: ThemeMode; onToggleTheme: () => void }) {
  const { user, isLoading } = useAuth()
  if (isLoading) return <div style={{ display: 'grid', placeItems: 'center', height: '100%' }}><Spinner /></div>
  if (!user) {
    return <Routes><Route path="/login" element={<LoginPage />} /><Route path="*" element={<Navigate to="/login" replace />} /></Routes>
  }
  const home = user.role === 'ADMINISTRATOR' ? '/situation' : '/incidents'
  return (
    <Routes>
      <Route element={<AppShell themeMode={themeMode} onToggleTheme={onToggleTheme} />}>
        <Route index element={<Navigate to={home} replace />} />
        <Route path="/login" element={<Navigate to={home} replace />} />
        <Route path="/incidents" element={<IncidentWorkspacePage />} />
        <Route path="/incidents/new" element={<ReportIncidentPage />} />
        <Route path="/incidents/:incidentId" element={<IncidentWorkspacePage />} />
        <Route path="/service-map" element={<RequireRole roles={['TECHNICIAN', 'ADMINISTRATOR']}><ServiceMapPage /></RequireRole>} />
        <Route path="/situation" element={<RequireRole roles={['ADMINISTRATOR']}><SituationPage /></RequireRole>} />
        <Route path="/reports" element={<RequireRole roles={['ADMINISTRATOR']}><ReportsPage /></RequireRole>} />
        <Route path="/administration" element={<RequireRole roles={['ADMINISTRATOR']}><AdministrationPage /></RequireRole>} />
        <Route path="/audit-log" element={<RequireRole roles={['ADMINISTRATOR']}><AuditLogPage /></RequireRole>} />
        <Route path="*" element={<Navigate to={home} replace />} />
      </Route>
    </Routes>
  )
}

export default function App() {
  const [themeMode, setThemeMode] = useState<ThemeMode>(() => {
    const stored = localStorage.getItem(THEME_STORAGE_KEY)
    if (stored === 'light' || stored === 'dark') return stored
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
  })
  useEffect(() => {
    document.documentElement.dataset.theme = themeMode
    localStorage.setItem(THEME_STORAGE_KEY, themeMode)
  }, [themeMode])

  return (
    <FluentProvider theme={themeMode === 'dark' ? darkTheme : lightTheme} style={{ height: '100%' }}>
      <BrowserRouter>
        <AuthProvider>
          <AppRoutes themeMode={themeMode} onToggleTheme={() => setThemeMode((mode) => (mode === 'light' ? 'dark' : 'light'))} />
        </AuthProvider>
      </BrowserRouter>
    </FluentProvider>
  )
}
