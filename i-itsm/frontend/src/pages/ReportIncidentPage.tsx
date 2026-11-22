import { Button, Field, Input, Radio, RadioGroup, Select, Textarea } from '@fluentui/react-components'
import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api, ApiError } from '../api/api-client'
import type { IncidentDetail, ReportAnalysis, Service } from '../api/types'
import { ErrorNotice } from '../components/ErrorNotice'
import { IncidentPriorityBadge } from '../components/IncidentPriorityBadge'
import { STATUS_LABEL, PRIORITY_LABEL } from '../features/incidents/incident-labels'
import { useAuth } from '../features/auth/auth-context'
import { useApiResource } from '../hooks/use-api-resource'
import { useDebouncedValue } from '../hooks/use-debounced-value'
import { useNotify } from '../hooks/notify-context'
import styles from './ReportIncidentPage.module.css'

const SCOPES = [
  { label: 'Just me', impact: 1, users: 1 },
  { label: 'My team', impact: 2, users: 10 },
  { label: 'My department', impact: 3, users: 50 },
  { label: 'Everyone in the company', impact: 4, users: 200 },
]
const URGENCIES = [
  { label: 'It can wait', value: 1 },
  { label: 'I need it this week', value: 2 },
  { label: 'I need it today', value: 3 },
  { label: 'Work is blocked right now', value: 4 },
]

export function ReportIncidentPage() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const notify = useNotify()
  const { data: services } = useApiResource<Service[]>('/services/')
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [serviceId, setServiceId] = useState('')
  const [scopeIndex, setScopeIndex] = useState(0)
  const [urgency, setUrgency] = useState(2)
  const [analysis, setAnalysis] = useState<ReportAnalysis | null>(null)
  const [error, setError] = useState<ApiError | null>(null)
  const [isSending, setIsSending] = useState(false)

  const scope = SCOPES[scopeIndex]
  const draft = useDebouncedValue({ title, description, serviceId, impact: scope.impact, users: scope.users, urgency }, 500)

  // Context-aware help: while the person writes, look for the service, similar reports and past fixes.
  useEffect(() => {
    if (`${draft.title} ${draft.description}`.trim().length < 8) { setAnalysis(null); return undefined }
    let cancelled = false
    api.post<ReportAnalysis>('/incidents/analyze/', {
      title: draft.title, description: draft.description, service: draft.serviceId ? Number(draft.serviceId) : null,
      impact: draft.impact, urgency: draft.urgency, affectedUsers: draft.users,
    }).then((result) => { if (!cancelled) setAnalysis(result) }).catch(() => undefined)
    return () => { cancelled = true }
  }, [draft])

  const detectedService = analysis?.services[0]
  const likelyDuplicates = analysis?.similar.filter((item) => item.level === 'likely_duplicate' && !item.reportedByMe) ?? []

  const submit = async () => {
    setIsSending(true); setError(null)
    try {
      const incident = await api.post<IncidentDetail>('/incidents/', {
        title, description, impact: scope.impact, urgency, affectedUsers: scope.users,
        service: serviceId ? Number(serviceId) : null,
      })
      notify('success', `${incident.code} reported`)
      navigate(`/incidents/${incident.id}`)
    } catch (failure) {
      setError(failure as ApiError)
    } finally { setIsSending(false) }
  }

  const join = async (incidentId: number) => {
    try {
      await api.post(`/incidents/${incidentId}/actions/`, { action: 'join' })
      notify('success', 'Added. You will get updates on this incident.')
      navigate(`/incidents/${incidentId}`)
    } catch (failure) { setError(failure as ApiError) }
  }

  return (
    <div className={styles['report-incident-page']}>
      <section className={styles['report-incident-page__form']}>
        <h1 className={styles['report-incident-page__heading']}>What's going wrong?</h1>
        <p className={styles['report-incident-page__lead']}>
          Describe it the way you would to a colleague. We'll work out the service and priority.
        </p>
        <Field label="Summary" required>
          <Input value={title} onChange={(_, data) => setTitle(data.value)} maxLength={140}
            placeholder="Payment application is unavailable" />
        </Field>
        <Field label="What happened?" hint="What you were doing, what you saw, and when it started." required>
          <Textarea value={description} rows={5} resize="vertical" onChange={(_, data) => setDescription(data.value)} />
        </Field>
        <Field label="Who is affected?">
          <RadioGroup value={String(scopeIndex)} onChange={(_, data) => setScopeIndex(Number(data.value))}>
            {SCOPES.map((option, index) => <Radio key={option.label} value={String(index)} label={option.label} />)}
          </RadioGroup>
        </Field>
        <Field label="How soon do you need it fixed?">
          <RadioGroup value={String(urgency)} onChange={(_, data) => setUrgency(Number(data.value))}>
            {URGENCIES.map((option) => <Radio key={option.value} value={String(option.value)} label={option.label} />)}
          </RadioGroup>
        </Field>
        <Field label="Affected service"
          hint={detectedService && !serviceId ? `Detected: ${detectedService.name}. Change it only if that is wrong.` : 'Detected from your description.'}>
          <Select value={serviceId} onChange={(_, data) => setServiceId(data.value)}>
            <option value="">{detectedService ? `Detect automatically (${detectedService.name})` : 'Detect automatically'}</option>
            {(services ?? []).filter((service) => service.isActive).map((service) => (
              <option key={service.id} value={service.id}>{service.name}</option>
            ))}
          </Select>
        </Field>
        {error && (
          <ErrorNotice message={error.message} />
        )}
        {error?.code === 'duplicate_incident' && (
          <p><Link to={`/incidents/${String(error.extra.existingId)}`}>Open the incident you already reported</Link></p>
        )}
        <div className={styles['report-incident-page__actions']}>
          <Button appearance="primary" disabled={isSending || title.trim().length < 5 || description.trim().length < 10}
            onClick={submit}>{isSending ? 'Sending' : likelyDuplicates.length ? 'Send as a new report' : 'Send report'}</Button>
          <Button appearance="subtle" onClick={() => navigate(-1)}>Cancel</Button>
        </div>
      </section>

      <aside className={styles['report-incident-page__context']} aria-live="polite">
        {!analysis && <p className={styles['report-incident-page__placeholder']}>
          As you type, anything related that is already known will show up here: similar reports, and fixes that worked before.
        </p>}

        {analysis && analysis.similar.length > 0 && (
          <section className={styles['report-incident-page__block']}>
            <h2>{likelyDuplicates.length ? 'This looks already reported' : 'Possibly related'}</h2>
            {analysis.similar.map((item) => (
              <div key={item.id} className={styles['report-incident-page__similar']}>
                <div className={styles['report-incident-page__similar-title']}>
                  {item.priority && <IncidentPriorityBadge priority={item.priority} />}
                  <Link to={`/incidents/${item.id}`}>{item.code}</Link> {item.title}
                </div>
                <div className={styles['report-incident-page__meta']}>
                  {STATUS_LABEL[item.status]} · {Math.round(item.score * 100)}% similar
                  {item.matchedTerms.length > 0 && ` · matches on ${item.matchedTerms.join(', ')}`}
                </div>
                {user?.role === 'EMPLOYEE' && !item.reportedByMe && !item.alreadyJoined && (
                  <Button size="small" appearance="secondary" onClick={() => join(item.id)}>I'm affected too</Button>
                )}
                {item.alreadyJoined && <span className={styles['report-incident-page__meta']}>You are already following this.</span>}
              </div>
            ))}
            <p className={styles['report-incident-page__explain']}>
              Adding yourself to an existing incident keeps one clear record and raises its priority as more people are affected.
            </p>
          </section>
        )}

        {analysis && analysis.resolutions.length > 0 && (
          <section className={styles['report-incident-page__block']}>
            <h2>Worked for a similar problem</h2>
            {analysis.resolutions.map((item) => (
              <div key={item.incidentId} className={styles['report-incident-page__similar']}>
                <div>{item.resolution}</div>
                <div className={styles['report-incident-page__meta']}>From {item.incidentCode} · {Math.round(item.score * 100)}% similar</div>
              </div>
            ))}
          </section>
        )}

        {analysis?.priority && (
          <section className={styles['report-incident-page__block']}>
            <h2>How we will treat it</h2>
            <div><IncidentPriorityBadge priority={analysis.priority.priority} showLabel /></div>
            <p className={styles['report-incident-page__explain']}>
              {PRIORITY_LABEL[analysis.priority.priority]} priority. {analysis.priority.rationale.join('. ')}.
            </p>
          </section>
        )}
      </aside>
    </div>
  )
}
