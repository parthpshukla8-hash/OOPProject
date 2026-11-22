import { Button, Field, Input, Popover, PopoverSurface, PopoverTrigger, Select, Tab, TabList } from '@fluentui/react-components'
import { Add20Regular, Dismiss16Regular, Filter20Regular, Search20Regular } from '@fluentui/react-icons'
import { useCallback, useEffect, useMemo, useRef } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import type { Category, IncidentSummary, Service, TechnicianWorkload } from '../api/types'
import { ErrorNotice } from '../components/ErrorNotice'
import { IncidentPriorityBadge } from '../components/IncidentPriorityBadge'
import { SlaMeter } from '../components/SlaMeter'
import { useAuth } from '../features/auth/auth-context'
import { IncidentDetailPanel } from '../features/incidents/IncidentDetailPanel'
import { describeStatus } from '../features/incidents/incident-labels'
import { formatRelativeTime } from '../hooks/format-time'
import { useApiResource } from '../hooks/use-api-resource'
import { useDebouncedValue } from '../hooks/use-debounced-value'
import { useState } from 'react'
import styles from './IncidentWorkspacePage.module.css'

const FILTER_KEYS = ['priority', 'status', 'sla_status', 'category', 'service', 'technician', 'date_from', 'date_to'] as const

export function IncidentWorkspacePage() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const { incidentId } = useParams()
  const [searchParams, setSearchParams] = useSearchParams()
  const searchInput = useRef<HTMLInputElement>(null)
  const isStaff = user?.role !== 'EMPLOYEE'
  const scope = searchParams.get('scope') ?? 'open'
  const [text, setText] = useState(searchParams.get('q') ?? '')
  const query = useDebouncedValue(text.trim(), 300)

  const params = useMemo(() => {
    const result: Record<string, string> = { scope: scope === 'all' ? '' : scope, q: query }
    FILTER_KEYS.forEach((key) => { result[key] = searchParams.get(key) ?? '' })
    return result
  }, [scope, query, searchParams])
  const list = useApiResource<IncidentSummary[]>('/incidents/', params, 30000)
  const incidents = list.data ?? []
  const activeFilterCount = FILTER_KEYS.filter((key) => searchParams.get(key)).length

  const updateParam = useCallback((key: string, value: string) => {
    const next = new URLSearchParams(searchParams)
    if (value) next.set(key, value); else next.delete(key)
    setSearchParams(next, { replace: true })
  }, [searchParams, setSearchParams])

  const open = useCallback((id: number) => navigate({ pathname: `/incidents/${id}`, search: searchParams.toString() }), [navigate, searchParams])

  // Keyboard: j / k move through the list, "/" jumps to search.
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement
      if (['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName) || target.isContentEditable || event.ctrlKey || event.metaKey) return
      if (event.key === '/') { event.preventDefault(); searchInput.current?.focus(); return }
      if (event.key !== 'j' && event.key !== 'k') return
      const index = incidents.findIndex((item) => String(item.id) === incidentId)
      const next = incidents[event.key === 'j' ? Math.min(index + 1, incidents.length - 1) : Math.max(index - 1, 0)]
      if (next) open(next.id)
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [incidents, incidentId, open])

  const emptyMessage = query
    ? 'Nothing matches that. Try describing the problem with different words.'
    : scope === 'open'
      ? user?.role === 'EMPLOYEE' ? 'Nothing open right now.' : 'Nothing waiting on you.'
      : 'No incidents here yet.'

  return (
    <div className={`${styles['incident-workspace']} ${incidentId ? styles['incident-workspace--detail-open'] : ''}`}>
      <section className={styles['incident-workspace__list']} aria-label="Incidents">
        <div className={styles['incident-workspace__toolbar']}>
          <Input ref={searchInput} contentBefore={<Search20Regular />} value={text} onChange={(_, data) => setText(data.value)}
            placeholder={isStaff ? 'Search by number, or describe the problem' : 'Search your incidents'}
            aria-label="Search incidents" className={styles['incident-workspace__search']}
            contentAfter={text ? <Button size="small" appearance="transparent" icon={<Dismiss16Regular />} aria-label="Clear search" onClick={() => setText('')} /> : undefined} />
          {isStaff && <FilterPopover searchParams={searchParams} onChange={updateParam} count={activeFilterCount} isAdministrator={user?.role === 'ADMINISTRATOR'}
            onClear={() => { const next = new URLSearchParams(searchParams); FILTER_KEYS.forEach((key) => next.delete(key)); setSearchParams(next, { replace: true }) }} />}
          <Button icon={<Add20Regular />} appearance="primary" onClick={() => navigate('/incidents/new')} aria-label="Report an incident" />
        </div>
        <TabList size="small" selectedValue={scope} onTabSelect={(_, data) => updateParam('scope', String(data.value))}>
          <Tab value="open">Open</Tab><Tab value="finished">Resolved</Tab><Tab value="all">All</Tab>
        </TabList>
        {query && <p className={styles['incident-workspace__hint']}>Ranked by how closely each incident matches your words.</p>}
        {list.error && <ErrorNotice message={list.error.message} onRetry={list.reload} />}
        <ul className={styles['incident-workspace__rows']}>
          {incidents.map((incident) => (
            <li key={incident.id}>
              <button type="button" onClick={() => open(incident.id)}
                className={`${styles['incident-row']} ${styles[`incident-row--${incident.priority.toLowerCase()}`]} ${String(incident.id) === incidentId ? styles['incident-row--selected'] : ''}`}>
                <div className={styles['incident-row__line']}>
                  <IncidentPriorityBadge priority={incident.priority} />
                  <span className={styles['incident-row__code']}>{incident.code}</span>
                  <span className={styles['incident-row__title']}>{incident.title}</span>
                </div>
                <div className={styles['incident-row__line']}>
                  <span className={styles['incident-row__meta']}>
                    {user ? describeStatus(incident, user.role) : ''}
                    {isStaff && incident.serviceName ? ` · ${incident.serviceName}` : ''} · {formatRelativeTime(incident.updatedAt)}
                  </span>
                  {isStaff && !['RESOLVED', 'VERIFIED', 'CLOSED'].includes(incident.status) && <SlaMeter sla={incident.sla} compact />}
                  {incident.searchScore !== null && <span className={styles['incident-row__meta']}>{Math.round(Math.min(incident.searchScore, 1) * 100)}%</span>}
                </div>
              </button>
            </li>
          ))}
        </ul>
        {!list.isLoading && incidents.length === 0 && !list.error && (
          <div className={styles['incident-workspace__empty']}>
            <p>{emptyMessage}</p>
            {!query && <Link to="/incidents/new">Report an incident</Link>}
          </div>
        )}
      </section>

      <section className={styles['incident-workspace__detail']}>
        {incidentId ? (
          <>
            <Button className={styles['incident-workspace__back']} appearance="subtle" onClick={() => navigate({ pathname: '/incidents', search: searchParams.toString() })}>Back to the list</Button>
            <IncidentDetailPanel key={incidentId} incidentId={Number(incidentId)} onChanged={list.reload} />
          </>
        ) : (
          <div className={styles['incident-workspace__placeholder']}>
            <p>Pick an incident to see its details.</p>
            <p className={styles['incident-workspace__hint']}>Use J and K to move through the list, and / to search.</p>
          </div>
        )}
      </section>
    </div>
  )
}

interface FilterPopoverProps {
  searchParams: URLSearchParams; onChange: (key: string, value: string) => void; onClear: () => void
  count: number; isAdministrator: boolean
}

function FilterPopover({ searchParams, onChange, onClear, count, isAdministrator }: FilterPopoverProps) {
  const categories = useApiResource<Category[]>('/categories/').data ?? []
  const services = useApiResource<Service[]>('/services/').data ?? []
  const technicians = useApiResource<TechnicianWorkload[]>(isAdministrator ? '/technicians/' : null).data ?? []
  const get = (key: string) => searchParams.get(key) ?? ''
  const choice = (key: string, label: string, options: [string, string][]) => (
    <Field label={label}>
      <Select value={get(key)} onChange={(_, data) => onChange(key, data.value)}>
        <option value="">Any</option>{options.map(([value, name]) => <option key={value} value={value}>{name}</option>)}
      </Select>
    </Field>
  )
  return (
    <Popover positioning="below-end">
      <PopoverTrigger disableButtonEnhancement>
        <Button icon={<Filter20Regular />} aria-label="Filters">{count > 0 ? count : ''}</Button>
      </PopoverTrigger>
      <PopoverSurface className={styles['incident-filters']}>
        {choice('priority', 'Priority', [['P1', 'P1 Critical'], ['P2', 'P2 High'], ['P3', 'P3 Medium'], ['P4', 'P4 Low']])}
        {choice('status', 'Status', [['CLASSIFIED', 'Unassigned'], ['ASSIGNED', 'Assigned'], ['ACKNOWLEDGED', 'Acknowledged'], ['IN_PROGRESS', 'In progress'], ['WAITING_FOR_INFO', 'Waiting for reporter'], ['RESOLVED', 'Resolved'], ['VERIFIED', 'Verified'], ['CLOSED', 'Closed']])}
        {choice('sla_status', 'Service level', [['on_track', 'On track'], ['at_risk', 'At risk'], ['breached', 'Breached'], ['met', 'Met']])}
        {choice('category', 'Category', categories.map((c) => [String(c.id), c.name]))}
        {choice('service', 'Service', services.map((s) => [String(s.id), s.name]))}
        {isAdministrator && choice('technician', 'Technician', technicians.map((t) => [String(t.id), t.name]))}
        <div className={styles['incident-filters__dates']}>
          <Field label="From"><Input type="date" value={get('date_from')} onChange={(_, d) => onChange('date_from', d.value)} /></Field>
          <Field label="To"><Input type="date" value={get('date_to')} onChange={(_, d) => onChange('date_to', d.value)} /></Field>
        </div>
        <Button appearance="subtle" onClick={onClear} disabled={count === 0}>Clear filters</Button>
      </PopoverSurface>
    </Popover>
  )
}
