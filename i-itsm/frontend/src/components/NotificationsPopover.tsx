import { Badge, Button, Popover, PopoverSurface, PopoverTrigger } from '@fluentui/react-components'
import { Alert20Regular } from '@fluentui/react-icons'
import { useNavigate } from 'react-router-dom'
import { api } from '../api/api-client'
import type { NotificationItem } from '../api/types'
import { formatRelativeTime } from '../hooks/format-time'
import { useApiResource } from '../hooks/use-api-resource'
import styles from './NotificationsPopover.module.css'

export function NotificationsPopover() {
  const { data, reload } = useApiResource<NotificationItem[]>('/notifications/', undefined, 30000)
  const navigate = useNavigate()
  const items = data ?? []
  const unread = items.filter((item) => !item.isRead).length

  const open = async (item: NotificationItem) => {
    if (!item.isRead) await api.post(`/notifications/${item.id}/read/`).catch(() => undefined)
    reload()
    if (item.incident) navigate(`/incidents/${item.incident}`)
  }

  return (
    <Popover positioning="after-end">
      <PopoverTrigger disableButtonEnhancement>
        <Button appearance="subtle" icon={<Alert20Regular />} aria-label={`Notifications, ${unread} unread`}>
          Notifications {unread > 0 && <Badge size="small" color="danger" style={{ marginLeft: 6 }}>{unread}</Badge>}
        </Button>
      </PopoverTrigger>
      <PopoverSurface className={styles['notifications-popover']}>
        <div className={styles['notifications-popover__header']}>
          <strong>Notifications</strong>
          {unread > 0 && (
            <Button size="small" appearance="transparent"
              onClick={async () => { await api.post('/notifications/read-all/'); reload() }}>Mark all read</Button>
          )}
        </div>
        {items.length === 0 && <p className={styles['notifications-popover__empty']}>Nothing yet. Updates on your incidents will show up here.</p>}
        <ul className={styles['notifications-popover__list']}>
          {items.map((item) => (
            <li key={item.id}>
              <button type="button" onClick={() => open(item)}
                className={`${styles['notifications-popover__item']} ${item.isRead ? '' : styles['notifications-popover__item--unread']}`}>
                <span>{item.subject}</span>
                <small>{formatRelativeTime(item.createdAt)}</small>
              </button>
            </li>
          ))}
        </ul>
      </PopoverSurface>
    </Popover>
  )
}
