import { Link } from 'react-router-dom'
import type { Situation } from '../api/types'
import { ErrorNotice } from '../components/ErrorNotice'
import { IncidentPriorityBadge } from '../components/IncidentPriorityBadge'
import { Sparkline } from '../components/Sparkline'
import { formatMinutes } from '../hooks/format-time'
import { useApiResource } from '../hooks/use-api-resource'
import { Spinner } from '@fluentui/react-components'
import styles from './SituationPage.module.css'

function headline(situation: Situation): string {
  const { overview, attention } = situation
  if (attention.length === 0 && overview.criticalOpen === 0) return 'Nothing needs you right now.'
  const parts: string[] = []
  if (attention.length) parts.push(`${attention.length} incident${attention.length === 1 ? ' needs' : 's need'} attention`)
  if (overview.criticalOpen) parts.push(`${overview.criticalOpen} critical ${overview.criticalOpen === 1 ? 'is' : 'are'} open`)
  return `${parts.join(', ')}.`
}

export function SituationPage() {
  const { data, error, isLoading, reload } = useApiResource<Situation>('/situation/', undefined, 30000)
  if (isLoading && !data) return <div className={styles['situation-page']}><Spinner label="Checking the situation" /></div>
  if (error && !data) return <div className={styles['situation-page']}><ErrorNotice message={error.message} onRetry={reload} /></div>
  if (!data) return null
  const { overview } = data

  return (
    <div className={styles['situation-page']}>
      <header className={styles['situation-page__header']}>
        <h1>{headline(data)}</h1>
        <p className={styles['situation-page__facts']}>
          {overview.open} open of {overview.total} in total · {overview.slaViolations} service level breaches
          {overview.averageResolutionMinutes !== null && ` · average fix time ${formatMinutes(overview.averageResolutionMinutes)}`}
          {' '}<Sparkline values={overview.dailyVolume.map((day) => day.count)} label="Incidents reported per day, last 14 days" />
        </p>
      </header>

      {data.attention.length > 0 && (
        <section className={styles['situation-page__section']}>
          <h2>Needs attention</h2>
          <ul className={styles['situation-page__list']}>
            {data.attention.map((item) => (
              <li key={item.incidentId} className={styles['situation-page__item']}>
                <IncidentPriorityBadge priority={item.priority} />
                <div>
                  <Link to={`/incidents/${item.incidentId}`}>{item.code} {item.title}</Link>
                  <div className={styles['situation-page__reason']}>
                    {item.reasons.join(' · ')}{item.assignee ? ` · with ${item.assignee}` : ''}
                  </div>
                </div>
              </li>
            ))}
          </ul>
        </section>
      )}

      {data.predictedBreaches.length > 0 && (
        <section className={styles['situation-page__section']}>
          <h2>Likely to miss their target</h2>
          <ul className={styles['situation-page__list']}>
            {data.predictedBreaches.map((item) => (
              <li key={item.incidentId} className={styles['situation-page__item']}>
                <IncidentPriorityBadge priority={item.priority} />
                <div className={styles['situation-page__grow']}>
                  <Link to={`/incidents/${item.incidentId}`}>{item.code} {item.title}</Link>
                  <div className={styles['situation-page__bar']}><span style={{ width: `${item.probability * 100}%` }} /></div>
                </div>
                <span className={styles['situation-page__reason']}>{Math.round(item.probability * 100)}%</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {data.correlations.length > 0 && (
        <section className={styles['situation-page__section']}>
          <h2>Reports that look like one problem</h2>
          <ul className={styles['situation-page__list']}>
            {data.correlations.map((cluster) => (
              <li key={cluster.incidentIds.join('-')} className={styles['situation-page__cluster']}>
                <div>
                  {cluster.size} reports{cluster.services.length > 0 && ` on ${cluster.services.join(', ')}`}
                  {cluster.topTerms.length > 0 && <span className={styles['situation-page__reason']}> · common words: {cluster.topTerms.join(', ')}</span>}
                </div>
                <div className={styles['situation-page__codes']}>
                  {cluster.incidentIds.map((id, index) => <Link key={id} to={`/incidents/${id}`}>{cluster.incidentCodes[index]}</Link>)}
                </div>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  )
}
