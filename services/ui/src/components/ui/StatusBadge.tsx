import { Badge } from './Badge'

const statusConfig: Record<string, { label: string; variant: 'success' | 'warning' | 'danger' | 'info' | 'default'; icon: string }> = {
  uploaded: { label: 'Uploaded', variant: 'info', icon: '\u2191' },
  ingested: { label: 'Ingested', variant: 'info', icon: '\u2713' },
  classified: { label: 'Classified', variant: 'info', icon: '\u2713' },
  extracted: { label: 'Extracted', variant: 'info', icon: '\u2713' },
  summarized: { label: 'Summarized', variant: 'success', icon: '\u2713' },
  generated: { label: 'Generated', variant: 'success', icon: '\u2713' },
  processed: { label: 'Processed', variant: 'success', icon: '\u2713' },
  completed: { label: 'Completed', variant: 'success', icon: '\u2713' },
  processing: { label: 'Processing', variant: 'warning', icon: '\u25CB' },
  running: { label: 'Running', variant: 'warning', icon: '\u25CB' },
  waiting_review: { label: 'Needs Review', variant: 'warning', icon: '!' },
  pending: { label: 'Pending', variant: 'default', icon: '\u2026' },
  failed: { label: 'Failed', variant: 'danger', icon: '\u2717' },
  none: { label: 'Not Started', variant: 'default', icon: '\u2014' },
}

interface StatusBadgeProps {
  status: string
}

export function StatusBadge({ status }: StatusBadgeProps) {
  const config = statusConfig[status] ?? { label: status, variant: 'default' as const, icon: '?' }
  return (
    <Badge variant={config.variant}>
      <span className="mr-1">{config.icon}</span>
      {config.label}
    </Badge>
  )
}
