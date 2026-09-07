/**
 * Persistent retry queue for study-progress writes.
 *
 * Reviews, quiz attempts and exam session records are never silently lost:
 * on any failure they are enqueued here (IndexedDB, shared with the service
 * worker's offline queue) and replayed FIFO with exponential backoff until
 * the server accepts them. 4xx responses are dropped with a warning — a bad
 * request will never succeed by retrying.
 *
 * Replay is scoped to the user who queued the write: rows are stamped with an
 * owner and only the current session's rows are sent. See `queueOwner.ts`.
 */

import {
  getQueueOwner,
  selectDrainable,
  type OwnedRow,
  type QueueOwner,
} from './queueOwner'

export interface QueuedWrite extends OwnedRow {
  id?: number
  url: string
  method: string
  body: string
  timestamp: number
}

export interface QueueStorage {
  add(item: Omit<QueuedWrite, 'id'>): Promise<number>
  getAll(): Promise<QueuedWrite[]>
  delete(id: number): Promise<void>
  count(): Promise<number>
}

// Same database/store the service worker uses, so both queues share one pool.
const DB_NAME = 'studyaio-offline'
const STORE_NAME = 'mutations'
const DB_VERSION = 1

function openDB(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION)
    req.onupgradeneeded = () => {
      const db = req.result
      if (!db.objectStoreNames.contains(STORE_NAME)) {
        db.createObjectStore(STORE_NAME, { keyPath: 'id', autoIncrement: true })
      }
    }
    req.onsuccess = () => resolve(req.result)
    req.onerror = () => reject(req.error)
  })
}

/** IndexedDB-backed storage adapter (production). */
export function createIndexedDBStorage(): QueueStorage {
  return {
    async add(item) {
      const db = await openDB()
      return new Promise((resolve, reject) => {
        const tx = db.transaction(STORE_NAME, 'readwrite')
        const req = tx.objectStore(STORE_NAME).add(item)
        tx.oncomplete = () => resolve(req.result as number)
        tx.onerror = () => reject(tx.error)
      })
    },
    async getAll() {
      const db = await openDB()
      return new Promise((resolve, reject) => {
        const tx = db.transaction(STORE_NAME, 'readonly')
        const req = tx.objectStore(STORE_NAME).getAll()
        req.onsuccess = () => resolve(req.result as QueuedWrite[])
        req.onerror = () => reject(req.error)
      })
    },
    async delete(id) {
      const db = await openDB()
      return new Promise((resolve, reject) => {
        const tx = db.transaction(STORE_NAME, 'readwrite')
        tx.objectStore(STORE_NAME).delete(id)
        tx.oncomplete = () => resolve()
        tx.onerror = () => reject(tx.error)
      })
    },
    async count() {
      const db = await openDB()
      return new Promise((resolve, reject) => {
        const tx = db.transaction(STORE_NAME, 'readonly')
        const req = tx.objectStore(STORE_NAME).count()
        req.onsuccess = () => resolve(req.result)
        req.onerror = () => reject(req.error)
      })
    },
  }
}

const MIN_BACKOFF_MS = 1_000
const MAX_BACKOFF_MS = 60_000

interface WriteQueueOptions {
  fetchFn?: typeof fetch
  /** When true (default), failures schedule retries and 'online' triggers a flush. */
  autoFlush?: boolean
  /** Who the current session belongs to; defaults to the persisted owner. */
  getOwner?: () => Promise<QueueOwner | undefined>
}

export class WriteQueue {
  private storage: QueueStorage
  private fetchFn: typeof fetch
  private autoFlush: boolean
  private getOwner: () => Promise<QueueOwner | undefined>
  private listeners = new Set<() => void>()
  private cachedSize = 0
  private backoffMs = 0
  private retryTimer: ReturnType<typeof setTimeout> | null = null
  private flushing = false
  private readyPromise: Promise<void>
  private onOnline = () => {
    this.backoffMs = 0
    void this.flush()
  }

  constructor(storage: QueueStorage, options: WriteQueueOptions = {}) {
    this.storage = storage
    this.fetchFn = options.fetchFn ?? ((...args) => fetch(...args))
    this.autoFlush = options.autoFlush ?? true
    this.getOwner = options.getOwner ?? getQueueOwner
    this.readyPromise = this.countOwn()
      .then((count) => {
        if (count !== this.cachedSize) {
          this.cachedSize = count
          this.notify()
        }
      })
      .catch(() => {})
    if (this.autoFlush && typeof window !== 'undefined') {
      window.addEventListener('online', this.onOnline)
    }
  }

  /** Resolves once the persisted size has been loaded. */
  ready(): Promise<void> {
    return this.readyPromise
  }

  /** Current number of queued writes (sync, reactive via subscribe). */
  size(): number {
    return this.cachedSize
  }

  /** Test/inspection hook: current retry backoff (0 = no pending backoff). */
  getBackoffMs(): number {
    return this.backoffMs
  }

  subscribe = (cb: () => void): (() => void) => {
    this.listeners.add(cb)
    return () => {
      this.listeners.delete(cb)
    }
  }

  private notify() {
    for (const cb of this.listeners) cb()
  }

  /**
   * Rows the current session may replay. Rows belonging to another user are
   * excluded from the count too: showing user B "3 queued" for user A's
   * writes would be a lie, and `usePendingSync` would keep asking the service
   * worker to replay rows it will never send.
   */
  private async countOwn(): Promise<number> {
    const owner = await this.resolveOwner()
    const rows = await this.storage.getAll()
    return selectDrainable(rows, owner).length
  }

  /** Never throws — a failed lookup means "drain nothing", not "drain all". */
  private async resolveOwner(): Promise<QueueOwner> {
    try {
      return (await this.getOwner()) ?? null
    } catch {
      return null
    }
  }

  private async refreshSize() {
    try {
      this.cachedSize = await this.countOwn()
    } catch {
      // keep last-known size
    }
    this.notify()
  }

  /** Persist a failed write for replay. Never throws. */
  async enqueue(req: { url: string; method: string; body: string }): Promise<void> {
    try {
      const owner = await this.resolveOwner()
      await this.storage.add({ ...req, owner, timestamp: Date.now() })
      await this.refreshSize()
    } catch (err) {
      console.warn('writeQueue: failed to persist write', err)
      return
    }
    if (this.autoFlush) void this.flush()
  }

  /**
   * Replay queued writes FIFO. Removes on 2xx, drops on 4xx (with warning),
   * keeps and backs off on 5xx/network failure.
   *
   * Only the current session's rows are replayed. Another user's rows are
   * skipped and left untouched — they are that user's unsynced work, and
   * sending them now would execute them under this session's cookies.
   */
  async flush(): Promise<void> {
    if (this.flushing) return
    this.flushing = true
    let failed = false
    try {
      const owner = await this.resolveOwner()
      const rows = selectDrainable(
        (await this.storage.getAll()).sort((a, b) => (a.id ?? 0) - (b.id ?? 0)),
        owner,
      )
      for (const row of rows) {
        let response: Response
        try {
          response = await this.fetchFn(row.url, {
            method: row.method,
            headers: { 'Content-Type': 'application/json' },
            body: row.body,
            credentials: 'same-origin',
          })
        } catch {
          failed = true
          break // still offline / server unreachable — retry later
        }

        if (response.ok) {
          if (row.id !== undefined) await this.storage.delete(row.id)
          continue
        }
        if (response.status >= 400 && response.status < 500) {
          console.warn(
            `writeQueue: dropping ${row.method} ${row.url} — server rejected it (${response.status})`,
          )
          if (row.id !== undefined) await this.storage.delete(row.id)
          continue
        }
        // 5xx — server will hopefully recover; keep and back off
        failed = true
        break
      }
    } finally {
      this.flushing = false
    }

    await this.refreshSize()

    if (failed) {
      this.backoffMs =
        this.backoffMs === 0
          ? MIN_BACKOFF_MS
          : Math.min(this.backoffMs * 2, MAX_BACKOFF_MS)
      if (this.autoFlush) this.scheduleRetry()
    } else {
      this.backoffMs = 0
    }
  }

  private scheduleRetry() {
    if (this.retryTimer) clearTimeout(this.retryTimer)
    this.retryTimer = setTimeout(() => {
      this.retryTimer = null
      void this.flush()
    }, this.backoffMs)
  }

  /** Detach listeners/timers (tests, teardown). */
  stop() {
    if (this.retryTimer) clearTimeout(this.retryTimer)
    this.retryTimer = null
    if (this.autoFlush && typeof window !== 'undefined') {
      window.removeEventListener('online', this.onOnline)
    }
  }
}

function createDefaultQueue(): WriteQueue {
  if (typeof indexedDB === 'undefined') {
    // Non-browser context (SSR/tests without IDB): memory-only fallback
    const rows: QueuedWrite[] = []
    let nextId = 1
    const memory: QueueStorage = {
      async add(item) {
        const id = nextId++
        rows.push({ ...item, id })
        return id
      },
      async getAll() {
        return [...rows]
      },
      async delete(id) {
        const idx = rows.findIndex((r) => r.id === id)
        if (idx >= 0) rows.splice(idx, 1)
      },
      async count() {
        return rows.length
      },
    }
    return new WriteQueue(memory)
  }
  return new WriteQueue(createIndexedDBStorage())
}

/** Shared app-wide queue for study writes. */
export const writeQueue = createDefaultQueue()
