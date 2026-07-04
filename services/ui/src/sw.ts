/// <reference lib="webworker" />
import { precacheAndRoute, cleanupOutdatedCaches } from 'workbox-precaching'
import { registerRoute, NavigationRoute } from 'workbox-routing'
import {
  NetworkFirst,
  StaleWhileRevalidate,
  CacheFirst,
} from 'workbox-strategies'
import { ExpirationPlugin } from 'workbox-expiration'

declare const self: ServiceWorkerGlobalScope

// ── Precache static assets injected by vite-plugin-pwa ───────
precacheAndRoute(self.__WB_MANIFEST)
cleanupOutdatedCaches()

// ── SPA navigation: serve cached index.html when offline ─────
const navigationHandler = new NetworkFirst({
  cacheName: 'navigation',
  networkTimeoutSeconds: 3,
})
registerRoute(new NavigationRoute(navigationHandler))

// ── Study API routes — StaleWhileRevalidate for offline study ─
registerRoute(
  ({ url }) =>
    url.pathname.startsWith('/api/study/due') ||
    url.pathname.startsWith('/api/assets/flashcards') ||
    url.pathname.startsWith('/api/assets/quiz') ||
    url.pathname.startsWith('/api/courses'),
  new StaleWhileRevalidate({
    cacheName: 'study-api',
    plugins: [
      new ExpirationPlugin({ maxEntries: 100, maxAgeSeconds: 24 * 60 * 60 }),
    ],
  }),
  'GET'
)

// ── General API — NetworkFirst with cache fallback ───────────
registerRoute(
  ({ url }) =>
    url.pathname.startsWith('/api/') &&
    !url.pathname.startsWith('/api/auth/') &&
    !url.pathname.startsWith('/api/study/review') &&
    !url.pathname.startsWith('/api/study/quiz-attempt'),
  new NetworkFirst({
    cacheName: 'api-general',
    networkTimeoutSeconds: 5,
    plugins: [
      new ExpirationPlugin({ maxEntries: 50, maxAgeSeconds: 60 * 60 }),
    ],
  }),
  'GET'
)

// ── Extraction images — CacheFirst (immutable) ──────────────
registerRoute(
  ({ url }) => url.pathname.startsWith('/api/files/extractions/'),
  new CacheFirst({
    cacheName: 'extraction-images',
    plugins: [
      new ExpirationPlugin({
        maxEntries: 200,
        maxAgeSeconds: 7 * 24 * 60 * 60,
      }),
    ],
  })
)

// ── Offline mutation queue (IndexedDB) ──────────────────────

const DB_NAME = 'studyaio-offline'
const STORE_NAME = 'mutations'
const DB_VERSION = 1

function openDB(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION)
    req.onupgradeneeded = () => {
      const db = req.result
      if (!db.objectStoreNames.contains(STORE_NAME)) {
        db.createObjectStore(STORE_NAME, {
          keyPath: 'id',
          autoIncrement: true,
        })
      }
    }
    req.onsuccess = () => resolve(req.result)
    req.onerror = () => reject(req.error)
  })
}

interface QueuedMutation {
  id?: number
  url: string
  method: string
  body: string
  timestamp: number
}

async function enqueue(mutation: Omit<QueuedMutation, 'id'>): Promise<void> {
  const db = await openDB()
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, 'readwrite')
    tx.objectStore(STORE_NAME).add(mutation)
    tx.oncomplete = () => resolve()
    tx.onerror = () => reject(tx.error)
  })
}

async function drainQueue(): Promise<number> {
  const db = await openDB()
  const mutations: QueuedMutation[] = await new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, 'readonly')
    const req = tx.objectStore(STORE_NAME).getAll()
    req.onsuccess = () => resolve(req.result)
    req.onerror = () => reject(req.error)
  })

  let replayed = 0
  for (const m of mutations) {
    try {
      const resp = await fetch(m.url, {
        method: m.method,
        headers: { 'Content-Type': 'application/json' },
        body: m.body,
        credentials: 'same-origin',
      })
      if (resp.ok) {
        // Remove from queue
        const delTx = db.transaction(STORE_NAME, 'readwrite')
        delTx.objectStore(STORE_NAME).delete(m.id!)
        await new Promise<void>((res) => {
          delTx.oncomplete = () => res()
        })
        replayed++
      }
    } catch {
      // Still offline or server error — leave in queue
      break
    }
  }
  return replayed
}

async function getPendingCount(): Promise<number> {
  const db = await openDB()
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, 'readonly')
    const req = tx.objectStore(STORE_NAME).count()
    req.onsuccess = () => resolve(req.result)
    req.onerror = () => reject(req.error)
  })
}

// ── Intercept offline mutations ─────────────────────────────

self.addEventListener('fetch', (event: FetchEvent) => {
  const { request } = event
  if (request.method !== 'POST') return

  const url = new URL(request.url)
  const isReview = url.pathname === '/api/study/review'
  const isQuizAttempt = url.pathname === '/api/study/quiz-attempt'

  if (!isReview && !isQuizAttempt) return

  event.respondWith(
    (async () => {
      try {
        const response = await fetch(request.clone())
        // Server errors (5xx) fall through to the queue — study writes are never lost
        if (response.status < 500) return response
      } catch {
        // Network failed — fall through to queue the mutation
      }

      const body = await request.text()
      await enqueue({
        url: request.url,
        method: request.method,
        body,
        timestamp: Date.now(),
      })

      // Notify clients about pending count
      const count = await getPendingCount()
      const clients = await self.clients.matchAll()
      for (const client of clients) {
        client.postMessage({ type: 'PENDING_COUNT', count })
      }

      // Return synthetic response
      if (isReview) {
        const parsed = JSON.parse(body)
        const synthetic = {
          id: crypto.randomUUID(),
          flashcard_id: parsed.flashcard_id,
          ease_factor: 2.5,
          interval_days: 1,
          repetition_count: 0,
          next_review_at: new Date(
            Date.now() + 24 * 60 * 60 * 1000
          ).toISOString(),
          last_reviewed_at: new Date().toISOString(),
        }
        return new Response(JSON.stringify(synthetic), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        })
      }

      // Quiz attempt — return simple success
      return new Response(JSON.stringify({ status: 'queued_offline' }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      })
    })()
  )
})

// ── Message handler for replay trigger ──────────────────────

self.addEventListener('message', (event: ExtendableMessageEvent) => {
  if (event.data?.type === 'REPLAY_MUTATIONS') {
    event.waitUntil(
      (async () => {
        const replayed = await drainQueue()
        const remaining = await getPendingCount()
        const clients = await self.clients.matchAll()
        for (const client of clients) {
          client.postMessage({
            type: 'SYNC_COMPLETE',
            replayed,
            remaining,
          })
        }
      })()
    )
  }

  if (event.data?.type === 'GET_PENDING_COUNT') {
    event.waitUntil(
      (async () => {
        const count = await getPendingCount()
        const clients = await self.clients.matchAll()
        for (const client of clients) {
          client.postMessage({ type: 'PENDING_COUNT', count })
        }
      })()
    )
  }
})

// ── Web Push notification handler ────────────────────────────
self.addEventListener('push', (event: PushEvent) => {
  const data = event.data?.json() ?? { title: 'StudyAIO', body: 'New notification' }
  event.waitUntil(
    self.registration.showNotification(data.title, {
      body: data.body,
      icon: '/pwa-192x192.png',
      badge: '/pwa-192x192.png',
      data: { url: data.url || '/' },
    })
  )
})

self.addEventListener('notificationclick', (event: NotificationEvent) => {
  event.notification.close()
  const url = event.notification.data?.url || '/'
  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clients) => {
      for (const client of clients) {
        if ('focus' in client) {
          client.focus()
          client.postMessage({ type: 'NAVIGATE', url })
          return
        }
      }
      return self.clients.openWindow(url)
    })
  )
})

// ── Skip waiting on install ─────────────────────────────────
self.addEventListener('install', () => {
  self.skipWaiting()
})

self.addEventListener('activate', (event: ExtendableEvent) => {
  event.waitUntil(self.clients.claim())
})
