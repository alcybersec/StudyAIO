/** Shared formatting helpers for dashboard widgets. */

export function relativeTime(dateStr: string | null): string {
  if (!dateStr) return ''
  // API returns UTC timestamps without Z suffix — ensure JS parses as UTC
  const iso = dateStr.endsWith('Z') ? dateStr : dateStr + 'Z'
  const diff = Date.now() - new Date(iso).getTime()
  const minutes = Math.floor(diff / 60_000)
  if (minutes < 1) return 'just now'
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  return `${Math.floor(hours / 24)}d ago`
}

export function daysUntil(dueDate: string, now: number): number {
  return Math.ceil((new Date(dueDate).getTime() - now) / 86_400_000)
}

export function deadlineToneClass(days: number): string {
  if (days <= 3) return 'text-red-fg'
  if (days <= 7) return 'text-amber-fg'
  return 'text-text-faint'
}
