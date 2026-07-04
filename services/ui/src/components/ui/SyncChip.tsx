import { useSyncExternalStore } from 'react'
import { RefreshCw } from 'lucide-react'
import { writeQueue } from '../../lib/writeQueue'

interface SyncChipProps {
  /** Pin the chip to the top-right corner (global shell mount). */
  floating?: boolean
}

/**
 * Small persistent chip shown while study writes are queued for retry
 * (offline OR server errors). Disappears when the queue is flushed.
 */
export function SyncChip({ floating }: SyncChipProps) {
  const count = useSyncExternalStore(writeQueue.subscribe, () => writeQueue.size())

  if (count === 0) return null

  return (
    <span
      role="status"
      className={`inline-flex items-center gap-1.5 text-[11px] font-medium bg-peri-soft text-peri-fg rounded-full px-2.5 py-1 ${
        floating ? 'fixed top-2 right-3 z-50 shadow-lg shadow-black/10' : ''
      }`}
    >
      <RefreshCw size={10} className="animate-spin" style={{ animationDuration: '2s' }} aria-hidden />
      {count} unsaved · syncing
    </span>
  )
}
