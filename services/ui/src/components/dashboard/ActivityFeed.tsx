import { Card, StatusBadge } from '../ui'
import type { ActivityItem } from '../../types'

function relativeTime(dateStr: string | null): string {
  if (!dateStr) return ''
  // API returns UTC timestamps without Z suffix — ensure JS parses as UTC
  const iso = dateStr.endsWith('Z') ? dateStr : dateStr + 'Z'
  const diff = Date.now() - new Date(iso).getTime()
  const minutes = Math.floor(diff / 60_000)
  if (minutes < 1) return 'just now'
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  return `${days}d ago`
}

interface ActivityFeedProps {
  items: ActivityItem[]
}

export function ActivityFeed({ items }: ActivityFeedProps) {
  if (items.length === 0) {
    return (
      <Card>
        <h2 className="text-sm font-semibold text-gray-900 mb-3">Recent Activity</h2>
        <p className="text-sm text-gray-500">No recent pipeline activity.</p>
      </Card>
    )
  }

  return (
    <Card padding={false}>
      <div className="px-6 pt-5 pb-2">
        <h2 className="text-sm font-semibold text-gray-900">Recent Activity</h2>
      </div>
      <ul className="divide-y divide-gray-100">
        {items.slice(0, 5).map((item) => (
          <li key={item.pipeline_run_id} className="px-6 py-3 flex items-center gap-3">
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-gray-900 truncate">
                {item.filename ?? 'Unknown file'}
              </p>
              <p className="text-xs text-gray-500 mt-0.5">
                Stage: {item.stage}
              </p>
            </div>
            <StatusBadge status={item.status} />
            <span className="text-xs text-gray-400 shrink-0 w-14 text-right">
              {relativeTime(item.completed_at ?? item.started_at)}
            </span>
          </li>
        ))}
      </ul>
    </Card>
  )
}
