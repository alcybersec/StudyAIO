import type { ReactNode } from 'react'
import { GripVertical } from 'lucide-react'
import { EmptyState, ErrorState, SectionLabel, SkeletonText } from '../../ui'
import type { WidgetState } from './widgetState'

interface WidgetShellProps {
  title: string
  state: WidgetState
  onRetry?: () => void
  emptyIcon?: string
  emptyTitle?: string
  emptyHint?: string
  emptyActionLabel?: string
  emptyActionTo?: string
  /** Skeleton mirroring the widget's real layout. Falls back to text rows. */
  skeleton?: ReactNode
  children?: ReactNode
}

/**
 * One widget = one isolated data region: it loads, empties, and fails alone.
 * A failing widget renders a compact ErrorState while its siblings keep working.
 */
export function WidgetShell({
  title,
  state,
  onRetry,
  emptyIcon,
  emptyTitle,
  emptyHint,
  emptyActionLabel,
  emptyActionTo,
  skeleton,
  children,
}: WidgetShellProps) {
  return (
    <section className="relative group/widget h-full overflow-auto bg-surface-1 border border-border rounded-xl p-3">
      <span
        className="absolute top-2.5 right-2.5 text-text-faint opacity-0 group-hover/widget:opacity-100 cursor-grab transition-opacity"
        aria-hidden
      >
        <GripVertical size={13} />
      </span>
      <SectionLabel>{title}</SectionLabel>
      {state === 'loading' && (skeleton ?? <SkeletonText lines={3} />)}
      {state === 'error' && <ErrorState compact title={`${title} couldn't load`} onRetry={onRetry} />}
      {state === 'empty' && (
        <EmptyState
          compact
          icon={emptyIcon}
          title={emptyTitle ?? 'Nothing here yet'}
          description={emptyHint}
          actionLabel={emptyActionLabel}
          actionTo={emptyActionTo}
        />
      )}
      {state === 'data' && children}
    </section>
  )
}
