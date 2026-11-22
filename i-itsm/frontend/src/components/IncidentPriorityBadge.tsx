import type { IncidentPriority } from '../api/types'
import { PRIORITY_LABEL } from '../features/incidents/incident-labels'
import styles from './IncidentPriorityBadge.module.css'

const TONE: Record<IncidentPriority, string> = {
  P1: 'critical', P2: 'high', P3: 'medium', P4: 'low',
}

export function IncidentPriorityBadge({ priority, showLabel = false }: { priority: IncidentPriority; showLabel?: boolean }) {
  return (
    <span className={`${styles['incident-priority-badge']} ${styles[`incident-priority-badge--${TONE[priority]}`]}`}
      title={`${priority}, ${PRIORITY_LABEL[priority].toLowerCase()}`}>
      {priority}{showLabel ? ` ${PRIORITY_LABEL[priority].toLowerCase()}` : ''}
    </span>
  )
}
