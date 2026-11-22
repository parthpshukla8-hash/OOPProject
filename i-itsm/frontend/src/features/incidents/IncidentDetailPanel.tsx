import {
  Button, Dialog, DialogActions, DialogBody, DialogContent, DialogSurface, DialogTitle, Field, Input, Select,
  Spinner, Switch, Textarea,
} from '@fluentui/react-components'
import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, ApiError } from '../../api/api-client'
import type {
  AuditEvent, Category, IncidentAction, IncidentDetail, IncidentInsights, Service, TechnicianWorkload,
} from '../../api/types'
import { ErrorNotice } from '../../components/ErrorNotice'
import { IncidentPriorityBadge } from '../../components/IncidentPriorityBadge'
import { IncidentTimeline } from '../../components/IncidentTimeline'
import type { TimelineEntry } from '../../components/IncidentTimeline'
import { SlaMeter } from '../../components/SlaMeter'
import { formatClock, formatRelativeTime } from '../../hooks/format-time'
import { useNotify } from '../../hooks/notify-context'
import { useApiResource } from '../../hooks/use-api-resource'
import { useAuth } from '../auth/auth-context'
import { AUDIT_ACTION_LABEL, describeStatus, STATUS_LABEL } from './incident-labels'
import styles from './IncidentDetailPanel.module.css'

interface IncidentDetailPanelProps { incidentId: number; onChanged: () => void }

export function IncidentDetailPanel({ incidentId, onChanged }: IncidentDetailPanelProps) {
  const { user } = useAuth()
  const notify = useNotify()
  const isStaff = user?.role !== 'EMPLOYEE'
  const detailResource = useApiResource<IncidentDetail>(`/incidents/${incidentId}/`, undefined, 30000)
  const insightsResource = useApiResource<IncidentInsights>(isStaff ? `/incidents/${incidentId}/insights/` : null)
  const auditResource = useApiResource<AuditEvent[]>(isStaff ? `/incidents/${incidentId}/audit/` : null)
  const technicians = useApiResource<TechnicianWorkload[]>(user?.role === 'ADMINISTRATOR' ? '/technicians/' : null)
  const incident = detailResource.data

  const [openKey, setOpenKey] = useState<string | null>(null)
  const [text, setText] = useState('')
  const [technicianId, setTechnicianId] = useState('')
  const [rating, setRating] = useState(0)
  const [comment, setComment] = useState('')
  const [isInternal, setIsInternal] = useState(true)
  const [error, setError] = useState<ApiError | null>(null)
  const [isEditing, setIsEditing] = useState(false)

  const reloadAll = () => { detailResource.reload(); insightsResource.reload(); auditResource.reload(); onChanged() }

  const send = async (path: string, body: unknown, success?: string) => {
    setError(null)
    try {
      await api.post(path, body)
      setOpenKey(null); setText(''); setComment(''); setRating(0)
      if (success) notify('success', success)
      reloadAll()
    } catch (failure) { setError(failure as ApiError) }
  }
  const act = (key: string, payload: Record<string, unknown> = {}, success?: string) =>
    send(`/incidents/${incidentId}/actions/`, { action: key, ...payload }, success)

  const timeline = useMemo<TimelineEntry[]>(() => {
    if (!incident) return []
    const entries: TimelineEntry[] = incident.comments
      .filter((item) => item.kind !== 'JOINED' || isStaff)
      .map((item) => ({
        key: `c${item.id}`, at: item.createdAt, who: item.author.displayName, text: item.body,
        tone: item.isInternal ? 'internal' : item.kind === 'INFO_REQUEST' ? 'question' : 'comment',
      }))
    if (isStaff) {
      (auditResource.data ?? []).filter((event) => event.action !== 'NoteAdded').forEach((event) => entries.push({
        key: `a${event.id}`, at: event.createdAt, tone: 'event',
        text: `${AUDIT_ACTION_LABEL[event.action] ?? event.action}. ${event.description}`,
      }))
    } else {
      const stamps: [string | null, string][] = [
        [incident.createdAt, 'Reported'], [incident.acknowledgedAt, 'A technician picked it up'],
        [incident.resolvedAt, 'Marked as resolved'], [incident.verifiedAt, 'You confirmed it works'],
        [incident.closedAt, 'Closed'],
      ]
      stamps.forEach(([at, label]) => { if (at) entries.push({ key: label, at, text: label, tone: 'event' }) })
    }
    return entries
  }, [incident, auditResource.data, isStaff])

  if (detailResource.isLoading && !incident) return <div className={styles['incident-detail-panel__loading']}><Spinner label="Loading incident" /></div>
  if (detailResource.error && !incident) return <div className={styles['incident-detail-panel']}><ErrorNotice message={detailResource.error.message} onRetry={detailResource.reload} /></div>
  if (!incident || !user) return null

  const isFinished = ['RESOLVED', 'VERIFIED', 'CLOSED'].includes(incident.status)
  const canEdit = !isFinished && (isStaff || (incident.reporter.id === user.id && ['NEW', 'CLASSIFIED', 'ASSIGNED'].includes(incident.status)))
  const insights = insightsResource.data
  const recommended = new Map((insights?.recommendations ?? []).map((item) => [item.technician.id, item]))
  const showPrediction = isStaff && incident.prediction && incident.prediction.probability >= 0.3 && !isFinished

  const renderAction = (action: IncidentAction) => {
    if (action.key === 'assign') {
      const options = [...(technicians.data ?? [])].sort((a, b) => Number(recommended.has(b.id)) - Number(recommended.has(a.id)))
      return (
        <div key={action.key} className={styles['incident-detail-panel__form']}>
          <Field label={incident.assignee ? 'Reassign' : 'Assign to'}>
            <Select value={technicianId} onChange={(_, data) => setTechnicianId(data.value)}>
              <option value="">Choose a technician</option>
              {options.map((tech) => (
                <option key={tech.id} value={tech.id}>
                  {tech.name} ({tech.active}/{tech.capacity}){recommended.has(tech.id) ? ' · suggested' : ''}
                </option>
              ))}
            </Select>
          </Field>
          {(insights?.recommendations ?? []).map((item) => (
            <div key={item.technician.id} className={styles['incident-detail-panel__muted']}>
              <Button size="small" appearance="transparent" onClick={() => setTechnicianId(String(item.technician.id))}>
                {item.technician.displayName}
              </Button> {Math.round(item.score)}/100 · {item.reasons.join(', ')}
            </div>
          ))}
          <Button appearance="secondary" disabled={!technicianId}
            onClick={() => send(`/incidents/${incidentId}/assign/`, { technician: Number(technicianId) }, 'Assigned')}>Assign</Button>
        </div>
      )
    }
    if (action.key === 'feedback') {
      return (
        <div key={action.key} className={styles['incident-detail-panel__form']}>
          <Field label="How well did the fix work?">
            <div className={styles['incident-detail-panel__rating']}>
              {[1, 2, 3, 4, 5].map((value) => (
                <Button key={value} size="small" appearance={rating === value ? 'primary' : 'secondary'} onClick={() => setRating(value)}>{value}</Button>
              ))}
            </div>
          </Field>
          <Textarea value={comment} onChange={(_, data) => setComment(data.value)} placeholder="Anything we should know? (optional)" />
          <Button appearance="secondary" disabled={!rating}
            onClick={() => send(`/incidents/${incidentId}/feedback/`, { rating, comment }, 'Thanks for the feedback')}>Send rating</Button>
        </div>
      )
    }
    if (action.needs) {
      return openKey === action.key ? (
        <div key={action.key} className={styles['incident-detail-panel__form']}>
          <Field label={action.needsLabel}>
            <Textarea value={text} rows={3} resize="vertical" onChange={(_, data) => setText(data.value)} autoFocus />
          </Field>
          {action.key === 'resolve' && (insights?.resolutions ?? []).length > 0 && (
            <div className={styles['incident-detail-panel__suggestions']}>
              <span className={styles['incident-detail-panel__muted']}>Fixed similar incidents before:</span>
              {insights!.resolutions.map((item) => (
                <Button key={item.incidentId} size="small" appearance="subtle" onClick={() => setText(item.resolution)}
                  title={`${item.incidentCode}, ${Math.round(item.score * 100)}% similar`}>
                  {item.resolution.length > 70 ? `${item.resolution.slice(0, 70)}...` : item.resolution}
                </Button>
              ))}
            </div>
          )}
          <div className={styles['incident-detail-panel__row']}>
            <Button appearance={action.primary ? 'primary' : 'secondary'} disabled={!text.trim()}
              onClick={() => act(action.key, { [action.needs as string]: text })}>{action.label}</Button>
            <Button appearance="subtle" onClick={() => { setOpenKey(null); setText('') }}>Cancel</Button>
          </div>
        </div>
      ) : (
        <Button key={action.key} appearance={action.primary ? 'primary' : 'secondary'}
          onClick={() => { setOpenKey(action.key); setText('') }}>{action.label}</Button>
      )
    }
    return (
      <Button key={action.key} appearance={action.primary ? 'primary' : 'secondary'}
        onClick={() => act(action.key, {}, action.key === 'join' ? 'Added. You will get updates.' : undefined)}>{action.label}</Button>
    )
  }

  const inlineActions = incident.availableActions.filter((a) => !['assign', 'feedback'].includes(a.key) && !(a.needs && openKey === a.key))
  const formActions = incident.availableActions.filter((a) => ['assign', 'feedback'].includes(a.key) || (a.needs && openKey === a.key))

  return (
    <article className={styles['incident-detail-panel']}>
      <header className={styles['incident-detail-panel__header']}>
        <div className={styles['incident-detail-panel__code']}>
          <span>{incident.code}</span><IncidentPriorityBadge priority={incident.priority} showLabel />
          {incident.escalationLevel > 1 && <span className={styles['incident-detail-panel__escalated']}>Escalated to {incident.escalationLabel.toLowerCase()}</span>}
        </div>
        <h2 className={styles['incident-detail-panel__title']}>{incident.title}</h2>
        <p className={styles['incident-detail-panel__muted']}>
          {describeStatus(incident, user.role)} · reported by {incident.reporter.id === user.id ? 'you' : incident.reporter.displayName} {formatRelativeTime(incident.createdAt)}
          {incident.serviceName && ` · ${incident.serviceName}`}{incident.categoryName && ` · ${incident.categoryName}`}
          {incident.affectedUsers > 1 && ` · ${incident.affectedUsers} people affected`}
        </p>
      </header>

      {error && <ErrorNotice message={error.message} />}

      {(incident.availableActions.length > 0) && (
        <section className={styles['incident-detail-panel__next']} aria-label="Next step">
          {incident.status === 'WAITING_FOR_INFO' && user.id === incident.reporter.id && (
            <p className={styles['incident-detail-panel__question']}>
              {[...incident.comments].reverse().find((c) => c.kind === 'INFO_REQUEST')?.body}
            </p>
          )}
          {inlineActions.length > 0 && <div className={styles['incident-detail-panel__row']}>{inlineActions.map(renderAction)}</div>}
          {formActions.map(renderAction)}
        </section>
      )}

      {!isFinished && (
        <section className={styles['incident-detail-panel__section']}>
          <SlaMeter sla={incident.sla} />
          <p className={styles['incident-detail-panel__muted']}>
            {incident.acknowledgedAt ? `Acknowledged at ${formatClock(incident.acknowledgedAt)}.` : incident.responseDueAt ? `First response due by ${formatClock(incident.responseDueAt)}.` : ''}
            {incident.resolutionDueAt && ` Resolution target ${formatClock(incident.resolutionDueAt)}.`}
          </p>
          {showPrediction && (
            <p className={styles['incident-detail-panel__warning']}>
              {Math.round(incident.prediction!.probability * 100)}% chance this misses its target, judged from similar past incidents and the technician's queue.
            </p>
          )}
        </section>
      )}

      <section className={styles['incident-detail-panel__section']}>
        <h3>What was reported</h3>
        <p className={styles['incident-detail-panel__prose']}>{incident.description}</p>
        {canEdit && <Button size="small" appearance="subtle" onClick={() => setIsEditing(true)}>Edit details</Button>}
      </section>

      {incident.resolution && (
        <section className={styles['incident-detail-panel__section']}>
          <h3>Resolution</h3>
          <p className={styles['incident-detail-panel__prose']}>{incident.resolution}</p>
          {incident.feedbackRating && <p className={styles['incident-detail-panel__muted']}>Rated {incident.feedbackRating} out of 5{incident.feedbackComment && `: ${incident.feedbackComment}`}</p>}
        </section>
      )}

      {isStaff && insights && (
        <section className={styles['incident-detail-panel__section']}>
          <h3>Worth knowing</h3>
          {incident.probableRootCauseDetail && (
            <p className={styles['incident-detail-panel__insight']}>
              Probably caused by <Link to={`/incidents/${incident.probableRootCauseDetail.id}`}>{incident.probableRootCauseDetail.code}</Link> on {incident.probableRootCauseDetail.service}, which this service relies on.
            </p>
          )}
          {incident.duplicateOfCode && <p className={styles['incident-detail-panel__insight']}>Looks like a duplicate of {incident.duplicateOfCode}.</p>}
          {insights.similar.map((item) => (
            <p key={item.id} className={styles['incident-detail-panel__insight']}>
              <Link to={`/incidents/${item.id}`}>{item.code}</Link> {item.title}
              <span className={styles['incident-detail-panel__muted']}> · {STATUS_LABEL[item.status]} · {Math.round(item.score * 100)}% similar{item.matchedTerms.length ? `, matches on ${item.matchedTerms.join(', ')}` : ''}</span>
            </p>
          ))}
          {insights.resolutions.map((item) => (
            <p key={item.incidentId} className={styles['incident-detail-panel__insight']}>
              Fixed {item.incidentCode} before: {item.resolution}
              <span className={styles['incident-detail-panel__muted']}> · {Math.round(item.score * 100)}% similar{item.solvedBy ? `, by ${item.solvedBy}` : ''}</span>
            </p>
          ))}
          {incident.priorityRationale.length > 0 && <p className={styles['incident-detail-panel__muted']}>Priority: {incident.priorityRationale.join('. ')}.</p>}
          {!incident.probableRootCauseDetail && !incident.duplicateOfCode && insights.similar.length === 0 && insights.resolutions.length === 0 && (
            <p className={styles['incident-detail-panel__muted']}>Nothing similar on record yet.</p>
          )}
        </section>
      )}

      <section className={styles['incident-detail-panel__section']}>
        <h3>Activity</h3>
        <IncidentTimeline entries={timeline} />
        {incident.status !== 'CLOSED' && (
          <div className={styles['incident-detail-panel__form']}>
            <Textarea value={comment} rows={2} resize="vertical" onChange={(_, data) => setComment(data.value)}
              placeholder={isStaff ? 'Add an investigation note' : 'Add more information'} aria-label="New note" />
            <div className={styles['incident-detail-panel__row']}>
              <Button appearance="secondary" disabled={!comment.trim()}
                onClick={() => send(`/incidents/${incidentId}/comments/`, { body: comment, isInternal: isStaff && isInternal })}>
                {isStaff ? 'Add note' : 'Add comment'}
              </Button>
              {isStaff && <Switch checked={isInternal} onChange={(_, data) => setIsInternal(data.checked)} label="Only staff can see this" />}
            </div>
          </div>
        )}
      </section>

      {isEditing && <EditDialog incident={incident} isStaff={isStaff}
        onClose={() => setIsEditing(false)} onSaved={() => { setIsEditing(false); reloadAll() }} />}
    </article>
  )
}

function EditDialog({ incident, isStaff, onClose, onSaved }: {
  incident: IncidentDetail; isStaff: boolean; onClose: () => void; onSaved: () => void
}) {
  const services = useApiResource<Service[]>('/services/').data ?? []
  const categories = useApiResource<Category[]>('/categories/').data ?? []
  const [form, setForm] = useState({
    title: incident.title, description: incident.description, impact: incident.impact, urgency: incident.urgency,
    affectedUsers: incident.affectedUsers, service: incident.service ?? 0, category: incident.category ?? 0,
  })
  const [error, setError] = useState<ApiError | null>(null)
  const set = (patch: Partial<typeof form>) => setForm((current) => ({ ...current, ...patch }))
  const save = async () => {
    try {
      const body: Record<string, unknown> = { title: form.title, description: form.description, impact: form.impact, urgency: form.urgency, affectedUsers: form.affectedUsers }
      if (isStaff) { body.service = form.service || undefined; body.category = form.category || undefined }
      await api.patch(`/incidents/${incident.id}/`, body)
      onSaved()
    } catch (failure) { setError(failure as ApiError) }
  }
  const levels = [1, 2, 3, 4]
  return (
    <Dialog open onOpenChange={(_, data) => { if (!data.open) onClose() }}>
      <DialogSurface>
        <DialogBody>
          <DialogTitle>Edit {incident.code}</DialogTitle>
          <DialogContent className={styles['incident-detail-panel__form']}>
            {error && <ErrorNotice message={error.message} />}
            <Field label="Summary"><Input value={form.title} onChange={(_, d) => set({ title: d.value })} /></Field>
            <Field label="Details"><Textarea value={form.description} rows={4} onChange={(_, d) => set({ description: d.value })} /></Field>
            <div className={styles['incident-detail-panel__row']}>
              <Field label="Impact (1-4)"><Select value={String(form.impact)} onChange={(_, d) => set({ impact: Number(d.value) })}>{levels.map((n) => <option key={n} value={n}>{n}</option>)}</Select></Field>
              <Field label="Urgency (1-4)"><Select value={String(form.urgency)} onChange={(_, d) => set({ urgency: Number(d.value) })}>{levels.map((n) => <option key={n} value={n}>{n}</option>)}</Select></Field>
              <Field label="People affected"><Input type="number" value={String(form.affectedUsers)} onChange={(_, d) => set({ affectedUsers: Math.max(1, Number(d.value) || 1) })} /></Field>
            </div>
            {isStaff && (
              <div className={styles['incident-detail-panel__row']}>
                <Field label="Service"><Select value={String(form.service)} onChange={(_, d) => set({ service: Number(d.value) })}>{services.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</Select></Field>
                <Field label="Category"><Select value={String(form.category)} onChange={(_, d) => set({ category: Number(d.value) })}>{categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</Select></Field>
              </div>
            )}
          </DialogContent>
          <DialogActions>
            <Button appearance="secondary" onClick={onClose}>Cancel</Button>
            <Button appearance="primary" onClick={save}>Save changes</Button>
          </DialogActions>
        </DialogBody>
      </DialogSurface>
    </Dialog>
  )
}
