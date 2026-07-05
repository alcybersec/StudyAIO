import { useEffect, useRef, type ReactNode } from 'react'
import { GripVertical } from 'lucide-react'
import { EmptyState, ErrorState, SectionLabel, SkeletonText } from '../../ui'
import type { WidgetState } from './widgetState'
import { useWidgetMeasure } from '../measureContext'

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
  const measure = useWidgetMeasure()
  const contentRef = useRef<HTMLDivElement>(null)

  // Report natural content height (card padding included) so the dashboard can
  // size and align this widget's grid cell. The section fills the cell via
  // h-full; the measured region is the un-stretched content, so the reading is
  // the true content height regardless of how tall the cell ends up.
  useEffect(() => {
    const el = contentRef.current
    if (!el || !measure) return
    const report = () => measure.onMeasure(measure.widgetKey, el.offsetHeight + 24)
    report()
    const ro = new ResizeObserver(report)
    ro.observe(el)
    return () => ro.disconnect()
  }, [measure, state, children])

  return (
    <section className="relative group/widget h-full overflow-hidden bg-surface-1 border border-border rounded-xl p-3">
      <span
        className="absolute top-2.5 right-2.5 text-text-faint opacity-0 group-hover/widget:opacity-100 cursor-grab transition-opacity"
        aria-hidden
      >
        <GripVertical size={13} />
      </span>
      <div ref={contentRef}>
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
      </div>
    </section>
  )
}
