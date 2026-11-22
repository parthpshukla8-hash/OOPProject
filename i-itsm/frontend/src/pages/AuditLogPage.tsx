import { Field, Input, Select, Spinner, Table, TableBody, TableCell, TableHeader, TableHeaderCell, TableRow } from '@fluentui/react-components'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import type { AuditEvent } from '../api/types'
import { ErrorNotice } from '../components/ErrorNotice'
import { AUDIT_ACTION_LABEL } from '../features/incidents/incident-labels'
import { formatDateTime } from '../hooks/format-time'
import { useApiResource } from '../hooks/use-api-resource'
import styles from './AuditLogPage.module.css'

export function AuditLogPage() {
  const [action, setAction] = useState('')
  const [codeText, setCodeText] = useState('')
  const incidentNumber = Number(codeText.replace(/\D/g, '')) || ''
  const { data, error, isLoading, reload } = useApiResource<AuditEvent[]>('/audit-events/', { action, incident: incidentNumber })
  return (
    <div className={styles['audit-log-page']}>
      <h1>Audit log</h1>
      <div className={styles['audit-log-page__filters']}>
        <Field label="Incident number"><Input value={codeText} onChange={(_, d) => setCodeText(d.value)} placeholder="INC0012" /></Field>
        <Field label="Action">
          <Select value={action} onChange={(_, d) => setAction(d.value)}>
            <option value="">Any action</option>
            {Object.entries(AUDIT_ACTION_LABEL).map(([key, label]) => <option key={key} value={key}>{label}</option>)}
          </Select>
        </Field>
      </div>
      {error && <ErrorNotice message={error.message} onRetry={reload} />}
      {isLoading && !data && <Spinner label="Loading" />}
      <Table size="small" aria-label="Audit log">
        <TableHeader><TableRow>
          <TableHeaderCell>Time</TableHeaderCell><TableHeaderCell>Incident</TableHeaderCell><TableHeaderCell>Who</TableHeaderCell>
          <TableHeaderCell>Action</TableHeaderCell><TableHeaderCell>Change</TableHeaderCell><TableHeaderCell>Details</TableHeaderCell>
        </TableRow></TableHeader>
        <TableBody>
          {(data ?? []).map((event) => (
            <TableRow key={event.id}>
              <TableCell>{formatDateTime(event.createdAt)}</TableCell>
              <TableCell>{event.incident ? <Link to={`/incidents/${event.incident}`}>{event.incidentCode}</Link> : '-'}</TableCell>
              <TableCell>{event.actor?.displayName ?? 'System'}</TableCell>
              <TableCell>{AUDIT_ACTION_LABEL[event.action] ?? event.action}</TableCell>
              <TableCell>{event.previousState || event.newState ? `${event.previousState || '-'} to ${event.newState || '-'}` : ''}</TableCell>
              <TableCell>{event.description}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
      {data && data.length === 0 && <p className={styles['audit-log-page__empty']}>No events match.</p>}
    </div>
  )
}
