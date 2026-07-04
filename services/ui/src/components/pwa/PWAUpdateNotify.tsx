import { useRegisterSW } from 'virtual:pwa-register/react'
import { toast } from 'sonner'
import { useEffect, useRef } from 'react'

const UPDATE_CHECK_INTERVAL = 60 * 60 * 1000 // 60 minutes

export function PWAUpdateNotify() {
  const updateIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const {
    offlineReady: [offlineReady, setOfflineReady],
    needRefresh: [needRefresh],
    updateServiceWorker,
  } = useRegisterSW({
    onRegisteredSW(_url, registration) {
      if (!registration) return
      if (updateIntervalRef.current !== null) clearInterval(updateIntervalRef.current)
      updateIntervalRef.current = setInterval(() => {
        registration.update()
      }, UPDATE_CHECK_INTERVAL)
    },
  })

  useEffect(() => {
    return () => {
      if (updateIntervalRef.current !== null) clearInterval(updateIntervalRef.current)
    }
  }, [])

  useEffect(() => {
    if (offlineReady) {
      toast.success('Ready to work offline', {
        duration: 4000,
        onAutoClose: () => setOfflineReady(false),
        onDismiss: () => setOfflineReady(false),
      })
    }
  }, [offlineReady, setOfflineReady])

  useEffect(() => {
    if (needRefresh) {
      toast('New version available', {
        duration: Infinity,
        action: {
          label: 'Reload',
          onClick: () => updateServiceWorker(true),
        },
      })
    }
  }, [needRefresh, updateServiceWorker])

  return null
}
