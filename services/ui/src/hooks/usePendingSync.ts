import { useCallback, useEffect, useSyncExternalStore } from 'react'
import { useOnlineStatus } from './useOnlineStatus'

let pendingCount = 0
const listeners = new Set<() => void>()

function subscribe(cb: () => void) {
  listeners.add(cb)
  return () => { listeners.delete(cb) }
}

function getSnapshot() {
  return pendingCount
}

function setPendingCount(count: number) {
  pendingCount = count
  listeners.forEach(cb => cb())
}

// Listen for messages from service worker
if (typeof navigator !== 'undefined' && 'serviceWorker' in navigator) {
  navigator.serviceWorker.addEventListener('message', (event) => {
    if (event.data?.type === 'PENDING_COUNT') {
      setPendingCount(event.data.count)
    }
    if (event.data?.type === 'SYNC_COMPLETE') {
      setPendingCount(event.data.remaining)
    }
  })
}

export function usePendingSync() {
  const isOnline = useOnlineStatus()
  const count = useSyncExternalStore(subscribe, getSnapshot)

  const requestReplay = useCallback(() => {
    // `?.` guards a null controller, not a missing `serviceWorker`. The API is
    // absent outside a secure context — any plain-HTTP deployment, which the
    // self-host compose file permits — and the throw happens in an effect, so
    // it takes the whole page into the error boundary rather than degrading.
    if (!('serviceWorker' in navigator)) return
    navigator.serviceWorker.controller?.postMessage({
      type: 'REPLAY_MUTATIONS',
    })
  }, [])

  // When coming back online, trigger replay
  useEffect(() => {
    if (isOnline && count > 0) {
      requestReplay()
    }
  }, [isOnline, count, requestReplay])

  // On mount, ask SW for current count
  useEffect(() => {
    if (!('serviceWorker' in navigator)) return
    navigator.serviceWorker.controller?.postMessage({
      type: 'GET_PENDING_COUNT',
    })
  }, [])

  return { pendingCount: count, isOnline, requestReplay }
}
