import { useCallback, useEffect, useState } from 'react'
import { api } from '../api/client'

type PushPermission = 'default' | 'granted' | 'denied' | 'unsupported'

interface PushState {
  permission: PushPermission
  subscribed: boolean
  loading: boolean
}

function urlBase64ToUint8Array(base64String: string): Uint8Array {
  const padding = '='.repeat((4 - (base64String.length % 4)) % 4)
  const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/')
  const rawData = window.atob(base64)
  const outputArray = new Uint8Array(rawData.length)
  for (let i = 0; i < rawData.length; i++) {
    outputArray[i] = rawData.charCodeAt(i)
  }
  return outputArray
}

export function usePushNotifications() {
  const [state, setState] = useState<PushState>({
    permission: 'PushManager' in window ? Notification.permission as PushPermission : 'unsupported',
    subscribed: false,
    loading: false,
  })

  // Check if already subscribed on mount
  useEffect(() => {
    if (!('serviceWorker' in navigator) || !('PushManager' in window)) return

    navigator.serviceWorker.ready.then(async (registration) => {
      const subscription = await registration.pushManager.getSubscription()
      setState((s) => ({ ...s, subscribed: !!subscription }))
    })
  }, [])

  const subscribe = useCallback(async () => {
    if (!('PushManager' in window)) return

    setState((s) => ({ ...s, loading: true }))

    try {
      // Get VAPID public key from server
      const { public_key } = await api.get<{ public_key: string }>('/notifications/push/vapid-key')

      // Request notification permission
      const permission = await Notification.requestPermission()
      if (permission !== 'granted') {
        setState((s) => ({ ...s, permission: permission as PushPermission, loading: false }))
        return
      }

      // Subscribe via Push API
      const registration = await navigator.serviceWorker.ready
      const subscription = await registration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(public_key),
      })

      const json = subscription.toJSON()

      // Send subscription to backend
      await api.post('/notifications/push/subscribe', {
        endpoint: json.endpoint,
        p256dh: json.keys?.p256dh,
        auth: json.keys?.auth,
      })

      setState({ permission: 'granted', subscribed: true, loading: false })
    } catch (err) {
      console.error('Push subscription failed:', err)
      setState((s) => ({ ...s, loading: false }))
    }
  }, [])

  const unsubscribe = useCallback(async () => {
    setState((s) => ({ ...s, loading: true }))

    try {
      const registration = await navigator.serviceWorker.ready
      const subscription = await registration.pushManager.getSubscription()

      if (subscription) {
        // Unsubscribe from backend
        await api.post('/notifications/push/unsubscribe', {
          endpoint: subscription.endpoint,
        })

        // Unsubscribe from browser
        await subscription.unsubscribe()
      }

      setState((s) => ({ ...s, subscribed: false, loading: false }))
    } catch (err) {
      console.error('Push unsubscribe failed:', err)
      setState((s) => ({ ...s, loading: false }))
    }
  }, [])

  return { ...state, subscribe, unsubscribe }
}
