import { formatDateTime } from '../hooks/format-time'
import styles from './IncidentTimeline.module.css'

export interface TimelineEntry {
  key: string
  at: string
  text: string
  who?: string
  tone: 'event' | 'comment' | 'internal' | 'question'
}

export function IncidentTimeline({ entries }: { entries: TimelineEntry[] }) {
  const ordered = [...entries].sort((a, b) => new Date(a.at).getTime() - new Date(b.at).getTime())
  return (
    <ol className={styles['incident-timeline']}>
      {ordered.map((entry) => (
        <li key={entry.key} className={`${styles['incident-timeline__entry']} ${styles[`incident-timeline__entry--${entry.tone}`]}`}>
          <time className={styles['incident-timeline__time']}>{formatDateTime(entry.at)}</time>
          <div className={styles['incident-timeline__text']}>
            {entry.who && <strong>{entry.who}</strong>}
            {entry.tone === 'internal' && <span className={styles['incident-timeline__tag']}>internal</span>}
            {entry.who ? ' ' : ''}{entry.text}
          </div>
        </li>
      ))}
    </ol>
  )
}
