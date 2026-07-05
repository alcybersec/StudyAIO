/** Bell badge rendering rule: dot at exactly 1 unread, number from 2, capped at 9+. */
export type BellBadge = { kind: 'none' } | { kind: 'dot' } | { kind: 'count'; label: string }

export function bellBadge(unreadCount: number): BellBadge {
  if (unreadCount <= 0) return { kind: 'none' }
  if (unreadCount === 1) return { kind: 'dot' }
  return { kind: 'count', label: unreadCount > 9 ? '9+' : String(unreadCount) }
}
