import { usePendingSync } from '../../hooks/usePendingSync'

export function OfflineBanner() {
  const { isOnline, pendingCount } = usePendingSync()

  if (isOnline && pendingCount === 0) return null

  return (
    <div
      className={`fixed top-0 inset-x-0 z-50 px-4 py-2 text-center text-sm font-medium ${
        !isOnline
          ? 'bg-amber-500 text-white'
          : 'bg-primary text-white'
      }`}
    >
      {!isOnline ? (
        pendingCount > 0
          ? `Offline — ${pendingCount} review${pendingCount !== 1 ? 's' : ''} saved locally`
          : 'You are offline — cached content available'
      ) : (
        `Syncing ${pendingCount} pending review${pendingCount !== 1 ? 's' : ''}...`
      )}
    </div>
  )
}
