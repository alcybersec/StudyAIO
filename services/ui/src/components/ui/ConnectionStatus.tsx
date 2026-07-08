import { useEffect, useRef, useSyncExternalStore } from 'react'
import { RefreshCw, WifiOff } from 'lucide-react'
import { toast } from 'sonner'
import { useOnlineStatus } from '../../hooks/useOnlineStatus'
import { usePendingSync } from '../../hooks/usePendingSync'
import { writeQueue } from '../../lib/writeQueue'

/**
 * Global connectivity banner rendered in the shell on every page.
 * States: offline (amber) / back online + syncing queued writes (peri) /
 * a success toast once the queue flushes.
 */
export function ConnectionStatus() {
  const isOnline = useOnlineStatus()
  const { pendingCount: swPending } = usePendingSync()
  const queueSize = useSyncExternalStore(writeQueue.subscribe, () => writeQueue.size())

  // Both queues share the same IndexedDB store — these are two snapshots of
  // the same pool, so take the larger one rather than summing.
  const queued = Math.max(queueSize, swPending)
  const hadQueuedRef = useRef(false)

  // Kick the client-side queue when connectivity returns
  useEffect(() => {
    if (isOnline && queued > 0) {
      void writeQueue.flush()
    }
  }, [isOnline, queued])

  // Success toast when the queue drains while online
  useEffect(() => {
    if (queued > 0) {
      hadQueuedRef.current = true
    } else if (hadQueuedRef.current && isOnline) {
      hadQueuedRef.current = false
      toast.success('All changes synced')
    }
  }, [queued, isOnline])

  if (isOnline && queued === 0) return null

  if (!isOnline) {
    return (
      <div
        role="status"
        aria-live="polite"
        className="flex items-center gap-2.5 bg-amber-soft border-b border-amber/25 text-amber-fg px-3.5 py-2.5 text-xs font-medium"
      >
        <WifiOff size={14} aria-hidden />
        You're offline — showing cached data. Study progress is being saved locally.
        {queued > 0 && (
          <span className="ml-auto flex items-center gap-1.5 font-mono text-[11px]">
            <RefreshCw size={11} className="animate-spin" style={{ animationDuration: '3s' }} aria-hidden />
            {queued} queued
          </span>
        )}
      </div>
    )
  }

  return (
    <div
      role="status"
      aria-live="polite"
      className="flex items-center gap-2.5 bg-peri-soft border-b border-peri/25 text-peri-fg px-3.5 py-2.5 text-xs font-medium"
    >
      <RefreshCw size={14} className="animate-spin" style={{ animationDuration: '2s' }} aria-hidden />
      Back online — syncing {queued} queued change{queued !== 1 ? 's' : ''}…
    </div>
  )
}
