/** Presentation helpers for inbox notifications (icon map + relative time). */
import { Bell, CalendarClock, FileCheck, Inbox, Zap, type LucideIcon } from 'lucide-react'

/** kind → icon, per the ShellNav prototype notification panel. */
export const NOTIFICATION_ICONS: Record<string, LucideIcon> = {
  pipeline: FileCheck,
  review: Inbox,
  achievement: Zap,
  deadline: CalendarClock,
}

export function notificationIcon(kind: string): LucideIcon {
  return NOTIFICATION_ICONS[kind] ?? Bell
}

/** Relative time for the mono timestamp. API returns UTC without a Z suffix. */
export function relativeTime(dateStr: string): string {
  const iso = dateStr.endsWith('Z') || dateStr.includes('+') ? dateStr : `${dateStr}Z`
  const diff = Date.now() - new Date(iso).getTime()
  const minutes = Math.floor(diff / 60_000)
  if (minutes < 1) return 'just now'
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  return `${days}d ago`
}
