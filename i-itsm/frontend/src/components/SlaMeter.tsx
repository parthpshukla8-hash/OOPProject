import type { SlaSnapshot } from '../api/types'
import { formatMinutes } from '../hooks/format-time'
import styles from './SlaMeter.module.css'

interface SlaMeterProps { sla: SlaSnapshot; compact?: boolean }

/** A thin bar for time used against the resolution target. The tick marks the 80% warning point. */
export function SlaMeter({ sla, compact = false }: SlaMeterProps) {
  const used = Math.min(Math.max(sla.resolutionProgress, 0), 1)
  const left = sla.minutesToResolutionDue
  let label = 'Target met'
  if (sla.status === 'breached') label = left !== null && left < 0 ? `${formatMinutes(left)} overdue` : 'Target missed'
  else if (sla.status !== 'met' && left !== null) label = `${formatMinutes(left)} left`
  return (
    <div className={`${styles['sla-meter']} ${compact ? styles['sla-meter--compact'] : ''}`}
      role="img" aria-label={`Service level: ${label}`}>
      <div className={styles['sla-meter__track']}>
        <div className={`${styles['sla-meter__fill']} ${styles[`sla-meter__fill--${sla.status.replace('_', '-')}`]}`}
          style={{ width: `${used * 100}%` }} />
        <div className={styles['sla-meter__warning-tick']} />
      </div>
      <span className={`${styles['sla-meter__label']} ${sla.status === 'breached' ? styles['sla-meter__label--breached'] : ''}`}>
        {label}
      </span>
    </div>
  )
}
