import {
  Spinner, Table, TableBody, TableCell, TableHeader, TableHeaderCell, TableRow,
} from '@fluentui/react-components'
import { Link } from 'react-router-dom'
import type { FullReport, IncidentPriority } from '../api/types'
import { ErrorNotice } from '../components/ErrorNotice'
import { IncidentPriorityBadge } from '../components/IncidentPriorityBadge'
import { Sparkline } from '../components/Sparkline'
import { STATUS_LABEL } from '../features/incidents/incident-labels'
import { formatMinutes } from '../hooks/format-time'
import { useApiResource } from '../hooks/use-api-resource'
import styles from './ReportsPage.module.css'

function Bars({ rows }: { rows: { name: string; count: number }[] }) {
  const max = Math.max(...rows.map((row) => row.count), 1)
  return (
    <ul className={styles['reports-page__bars']}>
      {rows.map((row) => (
        <li key={row.name}>
          <span className={styles['reports-page__bar-label']}>{row.name}</span>
          <span className={styles['reports-page__bar-track']}><span style={{ width: `${(row.count / max) * 100}%` }} /></span>
          <span className={styles['reports-page__bar-value']}>{row.count}</span>
        </li>
      ))}
    </ul>
  )
}

export function ReportsPage() {
  const { data, error, isLoading, reload } = useApiResource<FullReport>('/reports/')
  if (isLoading && !data) return <div className={styles['reports-page']}><Spinner label="Preparing reports" /></div>
  if (error && !data) return <div className={styles['reports-page']}><ErrorNotice message={error.message} onRetry={reload} /></div>
  if (!data) return null
  const priorities: IncidentPriority[] = ['P1', 'P2', 'P3', 'P4']

  return (
    <div className={styles['reports-page']}>
      <h1>Reports</h1>
      <section className={styles['reports-page__summary']}>
        <dl>
          <div><dt>Total incidents</dt><dd>{data.total}</dd></div>
          <div><dt>Open</dt><dd>{data.open}</dd></div>
          <div><dt>Critical and open</dt><dd>{data.criticalOpen}</dd></div>
          <div><dt>Resolved</dt><dd>{data.resolved}</dd></div>
          <div><dt>Service level breaches</dt><dd>{data.slaViolations}</dd></div>
          <div><dt>Average fix time</dt><dd>{data.averageResolutionMinutes !== null ? formatMinutes(data.averageResolutionMinutes) : 'none yet'}</dd></div>
          <div><dt>Satisfaction</dt><dd>{data.feedback.average !== null ? `${data.feedback.average} / 5 (${data.feedback.count})` : 'none yet'}</dd></div>
        </dl>
        <div><Sparkline values={data.dailyVolume.map((day) => day.count)} width={220} height={40} label="Incidents per day, last 14 days" />
          <div className={styles['reports-page__caption']}>Reported per day, last 14 days</div></div>
      </section>

      <div className={styles['reports-page__columns']}>
        <section><h2>By service</h2><Bars rows={data.byService.map((row) => ({ name: row.name ?? 'Unassigned', count: row.count }))} /></section>
        <section><h2>By category</h2><Bars rows={data.byCategory.map((row) => ({ name: row.name ?? 'Uncategorised', count: row.count }))} /></section>
        <section><h2>By status</h2><Bars rows={Object.entries(data.byStatus).map(([status, count]) => ({ name: STATUS_LABEL[status as keyof typeof STATUS_LABEL] ?? status, count }))} /></section>
      </div>

      <section>
        <h2>Priority and fix time</h2>
        <Table size="small" aria-label="Priority and fix time">
          <TableHeader><TableRow><TableHeaderCell>Priority</TableHeaderCell><TableHeaderCell>Incidents</TableHeaderCell><TableHeaderCell>Average fix time</TableHeaderCell></TableRow></TableHeader>
          <TableBody>
            {priorities.map((priority) => (
              <TableRow key={priority}>
                <TableCell><IncidentPriorityBadge priority={priority} showLabel /></TableCell>
                <TableCell>{data.byPriority[priority]}</TableCell>
                <TableCell>{data.averageResolutionByPriority[priority] !== null ? formatMinutes(data.averageResolutionByPriority[priority]!) : '-'}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </section>

      <section>
        <h2>Technician workload</h2>
        <Table size="small" aria-label="Technician workload">
          <TableHeader><TableRow><TableHeaderCell>Technician</TableHeaderCell><TableHeaderCell>Active</TableHeaderCell><TableHeaderCell>Resolved</TableHeaderCell><TableHeaderCell>Skills</TableHeaderCell></TableRow></TableHeader>
          <TableBody>
            {data.technicianWorkload.map((tech) => (
              <TableRow key={tech.id}>
                <TableCell>{tech.name}{!tech.isAvailable && ' (unavailable)'}</TableCell>
                <TableCell>
                  <span className={styles['reports-page__capacity']}><span style={{ width: `${Math.min(tech.active / tech.capacity, 1) * 100}%` }} /></span> {tech.active} of {tech.capacity}
                </TableCell>
                <TableCell>{tech.resolved}</TableCell>
                <TableCell>{tech.skills.join(', ')}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </section>

      {data.correlations.length > 0 && (
        <section>
          <h2>Related incidents</h2>
          {data.correlations.map((cluster) => (
            <p key={cluster.incidentIds.join('-')} className={styles['reports-page__line']}>
              {cluster.size} reports{cluster.services.length > 0 && ` on ${cluster.services.join(', ')}`}: {cluster.incidentIds.map((id, index) => (
                <span key={id}><Link to={`/incidents/${id}`}>{cluster.incidentCodes[index]}</Link>{index < cluster.size - 1 ? ', ' : ''}</span>
              ))}
            </p>
          ))}
        </section>
      )}
    </div>
  )
}
