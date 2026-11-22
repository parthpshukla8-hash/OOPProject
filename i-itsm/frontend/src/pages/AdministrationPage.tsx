import {
  Button, Checkbox, Dialog, DialogActions, DialogBody, DialogContent, DialogSurface, DialogTitle, Field, Input, Radio, RadioGroup,
  Select, Switch, Tab, TabList, Table, TableBody, TableCell, TableHeader, TableHeaderCell, TableRow, Textarea,
} from '@fluentui/react-components'
import { useState } from 'react'
import { api, ApiError } from '../api/api-client'
import type {
  Category, CurrentUser, IncidentPriority, NotificationItem, Service, ServiceDependency, SlaPolicy, SystemSettings,
} from '../api/types'
import { ErrorNotice } from '../components/ErrorNotice'
import { useNotify } from '../hooks/notify-context'
import { useApiResource } from '../hooks/use-api-resource'
import { formatDateTime } from '../hooks/format-time'
import styles from './AdministrationPage.module.css'

/** Runs a change, reports the outcome, and reloads what the page shows. */
function useChange(reload: () => void) {
  const notify = useNotify()
  const [error, setError] = useState<ApiError | null>(null)
  const run = async (work: () => Promise<unknown>, success: string) => {
    setError(null)
    try { await work(); notify('success', success); reload() } catch (failure) { setError(failure as ApiError) }
  }
  return { run, error }
}

export function AdministrationPage() {
  const [tab, setTab] = useState('strategies')
  return (
    <div className={styles['administration-page']}>
      <h1>Administration</h1>
      <TabList selectedValue={tab} onTabSelect={(_, data) => setTab(String(data.value))}>
        <Tab value="strategies">Strategies</Tab><Tab value="users">People</Tab><Tab value="services">Services</Tab>
        <Tab value="dependencies">Dependencies</Tab><Tab value="categories">Categories</Tab><Tab value="sla">Service levels</Tab>
        <Tab value="outbox">Outbox</Tab>
      </TabList>
      <div className={styles['administration-page__panel']}>
        {tab === 'strategies' && <StrategiesTab />}
        {tab === 'users' && <UsersTab />}
        {tab === 'services' && <ServicesTab />}
        {tab === 'dependencies' && <DependenciesTab />}
        {tab === 'categories' && <CategoriesTab />}
        {tab === 'sla' && <SlaTab />}
        {tab === 'outbox' && <OutboxTab />}
      </div>
    </div>
  )
}

function StrategiesTab() {
  const { data, reload } = useApiResource<SystemSettings>('/settings/')
  const { run, error } = useChange(reload)
  if (!data) return null
  const choose = (patch: Partial<Record<'assignmentStrategy' | 'priorityStrategy', string>>) =>
    run(() => api.put('/settings/', { assignmentStrategy: data.assignmentStrategy, priorityStrategy: data.priorityStrategy, ...patch }), 'Saved. New incidents will use it.')
  return (
    <div className={styles['administration-page__columns']}>
      {error && <ErrorNotice message={error.message} />}
      <Field label="How technicians are chosen">
        <RadioGroup value={data.assignmentStrategy} onChange={(_, d) => choose({ assignmentStrategy: d.value })}>
          {data.options.assignment.map((o) => <Radio key={o.key} value={o.key} label={<><strong>{o.label}</strong> <span className={styles['administration-page__muted']}>{o.description}</span></>} />)}
        </RadioGroup>
      </Field>
      <Field label="How priority is calculated">
        <RadioGroup value={data.priorityStrategy} onChange={(_, d) => choose({ priorityStrategy: d.value })}>
          {data.options.priority.map((o) => <Radio key={o.key} value={o.key} label={<><strong>{o.label}</strong> <span className={styles['administration-page__muted']}>{o.description}</span></>} />)}
        </RadioGroup>
      </Field>
    </div>
  )
}

function UsersTab() {
  const { data, reload } = useApiResource<CurrentUser[]>('/users/')
  const categories = useApiResource<Category[]>('/categories/').data ?? []
  const { run, error } = useChange(reload)
  const [isAdding, setIsAdding] = useState(false)
  const blank = { username: '', password: '', role: 'EMPLOYEE', firstName: '', lastName: '', email: '', experienceYears: 0, skillIds: [] as number[] }
  const [form, setForm] = useState(blank)
  return (
    <>
      {error && <ErrorNotice message={error.message} />}
      <Button appearance="primary" onClick={() => { setForm(blank); setIsAdding(true) }}>Add person</Button>
      <Table size="small" aria-label="People">
        <TableHeader><TableRow><TableHeaderCell>Name</TableHeaderCell><TableHeaderCell>Username</TableHeaderCell><TableHeaderCell>Role</TableHeaderCell><TableHeaderCell>Status</TableHeaderCell><TableHeaderCell /></TableRow></TableHeader>
        <TableBody>
          {(data ?? []).map((person) => (
            <TableRow key={person.id}>
              <TableCell>{person.displayName}</TableCell><TableCell>{person.username}</TableCell>
              <TableCell>{person.role.toLowerCase()}{person.isItManager ? ' (IT manager)' : ''}</TableCell>
              <TableCell>{!person.isActive ? 'Deactivated' : person.role === 'TECHNICIAN' ? `${person.activeIncidentCount} of ${person.maxActiveIncidents} active${person.isAvailable ? '' : ', unavailable'}` : 'Active'}</TableCell>
              <TableCell>{person.isActive && <Button size="small" appearance="subtle" onClick={() => run(() => api.delete(`/users/${person.id}/`), `${person.displayName} deactivated`)}>Deactivate</Button>}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
      <Dialog open={isAdding} onOpenChange={(_, d) => setIsAdding(d.open)}>
        <DialogSurface><DialogBody>
          <DialogTitle>Add a person</DialogTitle>
          <DialogContent className={styles['administration-page__form']}>
            <Field label="Username" required><Input value={form.username} onChange={(_, d) => setForm({ ...form, username: d.value })} /></Field>
            <Field label="Temporary password" required><Input type="password" value={form.password} onChange={(_, d) => setForm({ ...form, password: d.value })} /></Field>
            <div className={styles['administration-page__row']}>
              <Field label="First name"><Input value={form.firstName} onChange={(_, d) => setForm({ ...form, firstName: d.value })} /></Field>
              <Field label="Last name"><Input value={form.lastName} onChange={(_, d) => setForm({ ...form, lastName: d.value })} /></Field>
            </div>
            <Field label="Email"><Input value={form.email} onChange={(_, d) => setForm({ ...form, email: d.value })} /></Field>
            <Field label="Role"><Select value={form.role} onChange={(_, d) => setForm({ ...form, role: d.value })}>
              <option value="EMPLOYEE">Employee</option><option value="TECHNICIAN">Technician</option><option value="ADMINISTRATOR">Administrator</option></Select></Field>
            {form.role === 'TECHNICIAN' && (
              <>
                <Field label="Years of experience"><Input type="number" value={String(form.experienceYears)} onChange={(_, d) => setForm({ ...form, experienceYears: Number(d.value) || 0 })} /></Field>
                <Field label="Skills">
                  <div className={styles['administration-page__row']}>
                    {categories.map((c) => <Checkbox key={c.id} label={c.name} checked={form.skillIds.includes(c.id)}
                      onChange={(_, d) => setForm({ ...form, skillIds: d.checked ? [...form.skillIds, c.id] : form.skillIds.filter((id) => id !== c.id) })} />)}
                  </div>
                </Field>
              </>
            )}
          </DialogContent>
          <DialogActions>
            <Button appearance="secondary" onClick={() => setIsAdding(false)}>Cancel</Button>
            <Button appearance="primary" onClick={() => run(async () => { await api.post('/users/', form); setIsAdding(false) }, 'Person added')}>Add person</Button>
          </DialogActions>
        </DialogBody></DialogSurface>
      </Dialog>
    </>
  )
}

function ServicesTab() {
  const { data, reload } = useApiResource<Service[]>('/services/')
  const categories = useApiResource<Category[]>('/categories/').data ?? []
  const { run, error } = useChange(reload)
  const [draft, setDraft] = useState({ name: '', description: '', keywords: '', businessCriticality: 3, defaultCategory: '' })
  return (
    <>
      {error && <ErrorNotice message={error.message} />}
      <Table size="small" aria-label="Services">
        <TableHeader><TableRow><TableHeaderCell>Service</TableHeaderCell><TableHeaderCell>Business criticality</TableHeaderCell><TableHeaderCell>In use</TableHeaderCell></TableRow></TableHeader>
        <TableBody>
          {(data ?? []).map((service) => (
            <TableRow key={service.id}>
              <TableCell>{service.name}<div className={styles['administration-page__muted']}>{service.description}</div></TableCell>
              <TableCell><Select value={String(service.businessCriticality)} onChange={(_, d) => run(() => api.patch(`/services/${service.id}/`, { businessCriticality: Number(d.value) }), 'Criticality updated')}>
                {[1, 2, 3, 4, 5].map((n) => <option key={n} value={n}>{n}</option>)}</Select></TableCell>
              <TableCell><Switch checked={service.isActive} onChange={(_, d) => run(() => api.patch(`/services/${service.id}/`, { isActive: d.checked }), 'Saved')} /></TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
      <h2>Add a service</h2>
      <div className={styles['administration-page__form']}>
        <Field label="Name"><Input value={draft.name} onChange={(_, d) => setDraft({ ...draft, name: d.value })} /></Field>
        <Field label="Description"><Input value={draft.description} onChange={(_, d) => setDraft({ ...draft, description: d.value })} /></Field>
        <Field label="Words people use for it" hint="Used to recognise this service in new reports."><Textarea value={draft.keywords} onChange={(_, d) => setDraft({ ...draft, keywords: d.value })} /></Field>
        <div className={styles['administration-page__row']}>
          <Field label="Criticality"><Select value={String(draft.businessCriticality)} onChange={(_, d) => setDraft({ ...draft, businessCriticality: Number(d.value) })}>{[1, 2, 3, 4, 5].map((n) => <option key={n} value={n}>{n}</option>)}</Select></Field>
          <Field label="Usual category"><Select value={draft.defaultCategory} onChange={(_, d) => setDraft({ ...draft, defaultCategory: d.value })}><option value="">None</option>{categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</Select></Field>
        </div>
        <Button appearance="primary" disabled={!draft.name.trim()} onClick={() => run(() => api.post('/services/', { ...draft, defaultCategory: draft.defaultCategory ? Number(draft.defaultCategory) : null }), 'Service added')}>Add service</Button>
      </div>
    </>
  )
}

function DependenciesTab() {
  const { data, reload } = useApiResource<ServiceDependency[]>('/dependencies/')
  const services = useApiResource<Service[]>('/services/').data ?? []
  const { run, error } = useChange(reload)
  const [service, setService] = useState('')
  const [dependsOn, setDependsOn] = useState('')
  const name = (id: number) => services.find((s) => s.id === id)?.name ?? `#${id}`
  return (
    <>
      {error && <ErrorNotice message={error.message} />}
      <ul className={styles['administration-page__list']}>
        {(data ?? []).map((dependency) => (
          <li key={dependency.id}>
            <span>{name(dependency.service)} relies on {name(dependency.dependsOn)}</span>
            <Button size="small" appearance="subtle" onClick={() => run(() => api.delete(`/dependencies/${dependency.id}/`), 'Removed')}>Remove</Button>
          </li>
        ))}
      </ul>
      <div className={styles['administration-page__row']}>
        <Field label="Service"><Select value={service} onChange={(_, d) => setService(d.value)}><option value="">Choose</option>{services.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</Select></Field>
        <Field label="relies on"><Select value={dependsOn} onChange={(_, d) => setDependsOn(d.value)}><option value="">Choose</option>{services.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</Select></Field>
        <Button appearance="primary" disabled={!service || !dependsOn} onClick={() => run(() => api.post('/dependencies/', { service: Number(service), dependsOn: Number(dependsOn) }), 'Dependency added')}>Add</Button>
      </div>
    </>
  )
}

function CategoriesTab() {
  const { data, reload } = useApiResource<Category[]>('/categories/')
  const { run, error } = useChange(reload)
  const [name, setName] = useState('')
  const [keywords, setKeywords] = useState('')
  return (
    <>
      {error && <ErrorNotice message={error.message} />}
      <Table size="small" aria-label="Categories">
        <TableHeader><TableRow><TableHeaderCell>Category</TableHeaderCell><TableHeaderCell>Words that identify it</TableHeaderCell><TableHeaderCell /></TableRow></TableHeader>
        <TableBody>{(data ?? []).map((c) => (
          <TableRow key={c.id}><TableCell>{c.name}</TableCell><TableCell className={styles['administration-page__muted']}>{c.keywords}</TableCell>
            <TableCell><Button size="small" appearance="subtle" onClick={() => run(() => api.delete(`/categories/${c.id}/`), 'Removed')}>Remove</Button></TableCell></TableRow>
        ))}</TableBody>
      </Table>
      <div className={styles['administration-page__form']}>
        <Field label="New category"><Input value={name} onChange={(_, d) => setName(d.value)} /></Field>
        <Field label="Words that identify it" hint="New reports containing these words will be suggested this category."><Textarea value={keywords} onChange={(_, d) => setKeywords(d.value)} /></Field>
        <Button appearance="primary" disabled={!name.trim()} onClick={() => run(async () => { await api.post('/categories/', { name, keywords, description: '' }); setName(''); setKeywords('') }, 'Category added')}>Add category</Button>
      </div>
    </>
  )
}

function SlaTab() {
  const { data, reload } = useApiResource<SlaPolicy[]>('/sla-policies/')
  const services = useApiResource<Service[]>('/services/').data ?? []
  const { run, error } = useChange(reload)
  const [draft, setDraft] = useState({ priority: 'P1' as IncidentPriority, service: '', responseMinutes: 5, resolutionMinutes: 30 })
  const name = (id: number | null) => (id ? services.find((s) => s.id === id)?.name ?? `#${id}` : 'Everything else')
  return (
    <>
      {error && <ErrorNotice message={error.message} />}
      <Table size="small" aria-label="Service level policies">
        <TableHeader><TableRow><TableHeaderCell>Priority</TableHeaderCell><TableHeaderCell>Applies to</TableHeaderCell><TableHeaderCell>First response (min)</TableHeaderCell><TableHeaderCell>Resolution (min)</TableHeaderCell><TableHeaderCell /></TableRow></TableHeader>
        <TableBody>{(data ?? []).map((policy) => (
          <TableRow key={policy.id}>
            <TableCell>{policy.priority}</TableCell><TableCell>{name(policy.service)}</TableCell>
            {(['responseMinutes', 'resolutionMinutes'] as const).map((field) => (
              <TableCell key={field}><Input type="number" defaultValue={String(policy[field])} style={{ width: 90 }}
                onBlur={(event) => { const value = Number(event.target.value); if (value > 0 && value !== policy[field]) run(() => api.patch(`/sla-policies/${policy.id}/`, { [field]: value }), 'Saved') }} /></TableCell>
            ))}
            <TableCell>{policy.service && <Button size="small" appearance="subtle" onClick={() => run(() => api.delete(`/sla-policies/${policy.id}/`), 'Removed')}>Remove</Button>}</TableCell>
          </TableRow>
        ))}</TableBody>
      </Table>
      <h2>Add an override for one service</h2>
      <div className={styles['administration-page__row']}>
        <Field label="Priority"><Select value={draft.priority} onChange={(_, d) => setDraft({ ...draft, priority: d.value as IncidentPriority })}>{['P1', 'P2', 'P3', 'P4'].map((p) => <option key={p}>{p}</option>)}</Select></Field>
        <Field label="Service"><Select value={draft.service} onChange={(_, d) => setDraft({ ...draft, service: d.value })}><option value="">Choose</option>{services.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</Select></Field>
        <Field label="Response (min)"><Input type="number" value={String(draft.responseMinutes)} onChange={(_, d) => setDraft({ ...draft, responseMinutes: Number(d.value) })} /></Field>
        <Field label="Resolution (min)"><Input type="number" value={String(draft.resolutionMinutes)} onChange={(_, d) => setDraft({ ...draft, resolutionMinutes: Number(d.value) })} /></Field>
        <Button appearance="primary" disabled={!draft.service} onClick={() => run(() => api.post('/sla-policies/', { ...draft, service: Number(draft.service) }), 'Override added')}>Add</Button>
      </div>
    </>
  )
}

function OutboxTab() {
  const { data, error } = useApiResource<NotificationItem[]>('/notifications/outbox/', undefined, 15000)
  return (
    <>
      <p className={styles['administration-page__muted']}>Email and SMS are simulated. Every message that would have been sent is kept here.</p>
      {error && <ErrorNotice message={error.message} />}
      <Table size="small" aria-label="Simulated email and SMS">
        <TableHeader><TableRow><TableHeaderCell>When</TableHeaderCell><TableHeaderCell>Channel</TableHeaderCell><TableHeaderCell>To</TableHeaderCell><TableHeaderCell>Subject</TableHeaderCell></TableRow></TableHeader>
        <TableBody>{(data ?? []).map((m) => (
          <TableRow key={m.id}><TableCell>{formatDateTime(m.createdAt)}</TableCell><TableCell>{m.channel === 'SMS' ? 'SMS' : 'Email'}</TableCell><TableCell>{m.recipientName}</TableCell><TableCell>{m.subject}</TableCell></TableRow>
        ))}</TableBody>
      </Table>
    </>
  )
}
