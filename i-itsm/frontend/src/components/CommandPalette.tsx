import { Dialog, DialogBody, DialogSurface, Input } from '@fluentui/react-components'
import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import type { IncidentSummary, UserRole } from '../api/types'
import { useAuth } from '../features/auth/auth-context'
import { useApiResource } from '../hooks/use-api-resource'
import { useDebouncedValue } from '../hooks/use-debounced-value'
import { IncidentPriorityBadge } from './IncidentPriorityBadge'
import styles from './CommandPalette.module.css'

interface PaletteItem { id: string; label: string; hint?: string; run: () => void; priority?: IncidentSummary['priority'] }

const PAGES: { label: string; path: string; roles: UserRole[] }[] = [
  { label: 'Report an incident', path: '/incidents/new', roles: ['EMPLOYEE', 'TECHNICIAN', 'ADMINISTRATOR'] },
  { label: 'Incidents', path: '/incidents', roles: ['EMPLOYEE', 'TECHNICIAN', 'ADMINISTRATOR'] },
  { label: 'Situation', path: '/situation', roles: ['ADMINISTRATOR'] },
  { label: 'Service map', path: '/service-map', roles: ['TECHNICIAN', 'ADMINISTRATOR'] },
  { label: 'Reports', path: '/reports', roles: ['ADMINISTRATOR'] },
  { label: 'Administration', path: '/administration', roles: ['ADMINISTRATOR'] },
  { label: 'Audit log', path: '/audit-log', roles: ['ADMINISTRATOR'] },
]

interface CommandPaletteProps { open: boolean; onClose: () => void; onToggleTheme: () => void }

/** Jump anywhere: pages, or any incident by code or by describing it (ranked by cosine similarity). */
export function CommandPalette({ open, onClose, onToggleTheme }: CommandPaletteProps) {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [text, setText] = useState('')
  const [selectedIndex, setSelectedIndex] = useState(0)
  const query = useDebouncedValue(text.trim(), 250)
  const { data: found } = useApiResource<IncidentSummary[]>(open && query.length >= 2 ? '/incidents/' : null, { q: query })
  const listReference = useRef<HTMLUListElement>(null)

  useEffect(() => { if (open) { setText(''); setSelectedIndex(0) } }, [open])

  const items = useMemo<PaletteItem[]>(() => {
    const go = (path: string) => () => { onClose(); navigate(path) }
    const needle = text.trim().toLowerCase()
    const pages = PAGES.filter((page) => user && page.roles.includes(user.role) && page.label.toLowerCase().includes(needle))
      .map((page) => ({ id: page.path, label: page.label, hint: 'Go to', run: go(page.path) }))
    const actions = 'switch theme dark light'.includes(needle) && needle.length > 1
      ? [{ id: 'theme', label: 'Switch between light and dark', hint: 'Action', run: () => { onToggleTheme(); onClose() } }] : []
    const incidents = (found ?? []).slice(0, 6).map((incident) => ({
      id: `incident-${incident.id}`, label: `${incident.code}  ${incident.title}`, priority: incident.priority,
      hint: incident.searchScore ? `${Math.round(Math.min(incident.searchScore, 1) * 100)}% match` : undefined,
      run: go(`/incidents/${incident.id}`),
    }))
    return [...incidents, ...pages, ...actions]
  }, [text, found, user, navigate, onClose, onToggleTheme])

  const onKeyDown = (event: React.KeyboardEvent) => {
    if (event.key === 'ArrowDown') { event.preventDefault(); setSelectedIndex((index) => Math.min(index + 1, items.length - 1)) }
    if (event.key === 'ArrowUp') { event.preventDefault(); setSelectedIndex((index) => Math.max(index - 1, 0)) }
    if (event.key === 'Enter') items[selectedIndex]?.run()
  }

  return (
    <Dialog open={open} onOpenChange={(_, data) => { if (!data.open) onClose() }}>
      <DialogSurface className={styles['command-palette']} aria-label="Search and jump">
        <DialogBody className={styles['command-palette__body']}>
          <Input autoFocus appearance="underline" size="large" value={text} onKeyDown={onKeyDown}
            onChange={(_, data) => { setText(data.value); setSelectedIndex(0) }}
            placeholder="Type an incident number, or describe the problem" aria-label="Search" />
          <ul className={styles['command-palette__list']} ref={listReference} role="listbox">
            {items.map((item, index) => (
              <li key={item.id} role="option" aria-selected={index === selectedIndex}>
                <button type="button" onClick={item.run} onMouseEnter={() => setSelectedIndex(index)}
                  className={`${styles['command-palette__item']} ${index === selectedIndex ? styles['command-palette__item--selected'] : ''}`}>
                  {item.priority && <IncidentPriorityBadge priority={item.priority} />}
                  <span className={styles['command-palette__label']}>{item.label}</span>
                  {item.hint && <span className={styles['command-palette__hint']}>{item.hint}</span>}
                </button>
              </li>
            ))}
            {items.length === 0 && <li className={styles['command-palette__empty']}>No match. Try different words.</li>}
          </ul>
        </DialogBody>
      </DialogSurface>
    </Dialog>
  )
}
