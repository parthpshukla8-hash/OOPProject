import {
  Button, Menu, MenuItem, MenuList, MenuPopover, MenuTrigger, Toast, ToastTitle, Toaster, useId, useToastController,
} from '@fluentui/react-components'
import {
  Add20Regular, DataBarVertical20Regular, History20Regular, MailInbox20Regular, Organization20Regular, Person20Regular,
  Search20Regular, Settings20Regular, TextBulletListLtr20Regular, Flash20Regular,
} from '@fluentui/react-icons'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import type { UserRole } from '../api/types'
import { api } from '../api/api-client'
import { useAuth } from '../features/auth/auth-context'
import { NotifyContext } from '../hooks/notify-context'
import type { NoticeIntent } from '../hooks/notify-context'
import { CommandPalette } from './CommandPalette'
import { NotificationsPopover } from './NotificationsPopover'
import styles from './AppShell.module.css'

interface NavEntry { to: string; label: string; icon: JSX.Element; end?: boolean }

function navigationFor(role: UserRole): NavEntry[] {
  switch (role) {
    case 'ADMINISTRATOR':
      return [
        { to: '/situation', label: 'Situation', icon: <Flash20Regular /> },
        { to: '/incidents', label: 'Incidents', icon: <TextBulletListLtr20Regular />, end: true },
        { to: '/service-map', label: 'Service map', icon: <Organization20Regular /> },
        { to: '/reports', label: 'Reports', icon: <DataBarVertical20Regular /> },
        { to: '/administration', label: 'Administration', icon: <Settings20Regular /> },
        { to: '/audit-log', label: 'Audit log', icon: <History20Regular /> },
      ]
    case 'TECHNICIAN':
      return [
        { to: '/incidents', label: 'My queue', icon: <MailInbox20Regular />, end: true },
        { to: '/service-map', label: 'Service map', icon: <Organization20Regular /> },
        { to: '/incidents/new', label: 'Report an incident', icon: <Add20Regular /> },
      ]
    default:
      return [
        { to: '/incidents', label: 'My incidents', icon: <MailInbox20Regular />, end: true },
        { to: '/incidents/new', label: 'Report an incident', icon: <Add20Regular /> },
      ]
  }
}

interface AppShellProps { themeMode: 'light' | 'dark'; onToggleTheme: () => void }

export function AppShell({ themeMode, onToggleTheme }: AppShellProps) {
  const { user, logout, refreshUser } = useAuth()
  const navigate = useNavigate()
  const [paletteOpen, setPaletteOpen] = useState(false)
  const toasterId = useId('toaster')
  const { dispatchToast } = useToastController(toasterId)

  const notify = useCallback((intent: NoticeIntent, message: string) => {
    dispatchToast(<Toast><ToastTitle>{message}</ToastTitle></Toast>, { intent, timeout: 4000 })
  }, [dispatchToast])

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault()
        setPaletteOpen((open) => !open)
      }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [])

  const entries = useMemo(() => (user ? navigationFor(user.role) : []), [user])
  if (!user) return null

  return (
    <NotifyContext.Provider value={notify}>
      <div className={styles['app-shell']}>
        <nav className={styles['app-shell__rail']} aria-label="Main">
          <div className={styles['app-shell__brand']}>I-ITSM</div>
          <Button appearance="subtle" icon={<Search20Regular />} onClick={() => setPaletteOpen(true)}
            className={styles['app-shell__search']}>
            Search or jump <kbd className={styles['app-shell__shortcut']}>Ctrl K</kbd>
          </Button>
          <ul className={styles['app-shell__links']}>
            {entries.map((entry) => (
              <li key={entry.to}>
                <NavLink to={entry.to} end={entry.end}
                  className={({ isActive }) => `${styles['app-shell__link']} ${isActive ? styles['app-shell__link--active'] : ''}`}>
                  {entry.icon}<span>{entry.label}</span>
                </NavLink>
              </li>
            ))}
          </ul>
          <div className={styles['app-shell__footer']}>
            <NotificationsPopover />
            <Menu>
              <MenuTrigger disableButtonEnhancement>
                <Button appearance="subtle" icon={<Person20Regular />} className={styles['app-shell__user']}>
                  {user.displayName}
                </Button>
              </MenuTrigger>
              <MenuPopover>
                <MenuList>
                  {user.role === 'TECHNICIAN' && (
                    <MenuItem onClick={async () => {
                      await api.patch('/auth/me/', { isAvailable: !user.isAvailable })
                      await refreshUser()
                      notify('info', user.isAvailable ? 'You will not receive new assignments' : 'You can receive assignments again')
                    }}>{user.isAvailable ? 'Mark myself unavailable' : 'Mark myself available'}</MenuItem>
                  )}
                  <MenuItem onClick={() => navigate('/change-password')}>Change password</MenuItem>
                  <MenuItem onClick={onToggleTheme}>{themeMode === 'light' ? 'Dark theme' : 'Light theme'}</MenuItem>
                  <MenuItem onClick={() => logout()}>Sign out</MenuItem>
                </MenuList>
              </MenuPopover>
            </Menu>
          </div>
        </nav>
        <main className={styles['app-shell__content']}><Outlet /></main>
        <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} onToggleTheme={onToggleTheme} />
        <Toaster toasterId={toasterId} position="bottom-end" />
      </div>
    </NotifyContext.Provider>
  )
}
