export function formatMinutes(totalMinutes: number): string {
  const minutes = Math.round(Math.abs(totalMinutes))
  if (minutes < 60) return `${minutes}m`
  if (minutes < 60 * 24) {
    const remainder = minutes % 60
    return remainder ? `${Math.floor(minutes / 60)}h ${remainder}m` : `${Math.floor(minutes / 60)}h`
  }
  return `${Math.round(minutes / (60 * 24))}d`
}

export function formatRelativeTime(iso: string, now = Date.now()): string {
  const minutes = (now - new Date(iso).getTime()) / 60000
  if (minutes < 1) return 'just now'
  if (minutes < 60) return `${Math.round(minutes)} min ago`
  if (minutes < 60 * 24) return `${Math.round(minutes / 60)} h ago`
  return `${Math.round(minutes / (60 * 24))} d ago`
}

export const formatClock = (iso: string) =>
  new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })

export const formatDateTime = (iso: string) =>
  new Date(iso).toLocaleString([], { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })
