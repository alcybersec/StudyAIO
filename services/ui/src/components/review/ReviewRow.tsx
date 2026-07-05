import { FileQuestion } from 'lucide-react'
import { Badge, Button } from '../ui'
import { ReviewEditRow } from './ReviewEditRow'
import {
  approveResolution,
  confidenceTone,
  itemConfidencePct,
  itemFilename,
  itemGuess,
  itemReason,
} from './reviewUtils'
import type { CourseListItem, ReviewItem } from '../../types'

interface ReviewRowProps {
  item: ReviewItem
  focused: boolean
  editing: boolean
  busy: boolean
  courses: CourseListItem[]
  onFocus: () => void
  onApprove: () => void
  onEdit: () => void
  onDismiss: () => void
  onConfirmEdit: (resolution: Record<string, unknown>) => void
  onCancelEdit: () => void
}

/** One dense triage row: mono filename, pipeline guess, confidence, actions. */
export function ReviewRow({
  item,
  focused,
  editing,
  busy,
  courses,
  onFocus,
  onApprove,
  onEdit,
  onDismiss,
  onConfirmEdit,
  onCancelEdit,
}: ReviewRowProps) {
  const guess = itemGuess(item)
  const confidence = itemConfidencePct(item)
  const filename = itemFilename(item)
  const reason = itemReason(item)
  const pending = item.status === 'pending'
  const approvable = approveResolution(item) !== null

  return (
    <li
      aria-current={focused ? 'true' : undefined}
      onClick={onFocus}
      className={`px-3 py-2.5 transition-colors ${
        focused
          ? 'bg-surface-2 border-l-2 border-l-peri'
          : 'border-l-2 border-l-transparent hover:bg-surface-2/50'
      }`}
    >
      <div className="flex items-center gap-3">
        <FileQuestion size={14} className="text-text-faint shrink-0" aria-hidden />
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2.5 flex-wrap">
            <span className="font-mono text-[13px] text-text">
              {filename ?? item.review_type}
            </span>
            {guess.courseCode && (
              <span className="text-[13px] text-text-muted">
                → <span className="text-text font-medium">{guess.courseCode}</span>
                {guess.week !== null && <> · wk {guess.week}</>}
              </span>
            )}
            {confidence !== null && (
              <Badge variant={confidenceTone(confidence)}>{confidence}% confident</Badge>
            )}
            {!pending && (
              <Badge variant={item.status === 'resolved' ? 'success' : 'default'}>
                {item.status}
              </Badge>
            )}
          </div>
          {reason && <p className="text-xs text-text-muted mt-0.5 truncate">{reason}</p>}
        </div>
        {pending && (
          <div className="flex items-center gap-1.5 shrink-0">
            {approvable && (
              <Button size="sm" kbd="A" onClick={onApprove} disabled={busy}>
                Approve
              </Button>
            )}
            <Button variant="secondary" size="sm" kbd="E" onClick={onEdit} disabled={busy}>
              Edit
            </Button>
            <Button variant="ghost" size="sm" kbd="D" onClick={onDismiss} disabled={busy}>
              Dismiss
            </Button>
          </div>
        )}
        {!pending && item.resolved_at && (
          <span className="text-xs text-text-faint shrink-0">
            {new Date(item.resolved_at).toLocaleDateString()}
          </span>
        )}
      </div>

      {editing && pending && (
        <ReviewEditRow
          item={item}
          courses={courses}
          busy={busy}
          onConfirm={onConfirmEdit}
          onCancel={onCancelEdit}
        />
      )}
    </li>
  )
}
