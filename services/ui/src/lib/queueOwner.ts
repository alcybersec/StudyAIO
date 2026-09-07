/**
 * Ownership of the offline write queue.
 *
 * The offline mutation queue (IndexedDB `studyaio-offline` / `mutations`) is
 * drained with `credentials: 'same-origin'`, i.e. as whoever is signed in when
 * the drain runs. Before this module existed nothing tied a queued row to the
 * user who created it, so on a shared browser profile user A's queued writes
 * replayed against user B's session and were attributed to B (issue #73).
 *
 * Every row is now stamped with the id of the user who enqueued it, and both
 * drainers — `WriteQueue.flush()` on the page and `drainQueue()` in the
 * service worker — replay only the rows belonging to the current session.
 * Rows belonging to somebody else are left in place rather than deleted: they
 * are that person's unsynced work and drain normally when they sign back in
 * on this device.
 *
 * The owner is persisted in its own IndexedDB database rather than in a new
 * object store inside `studyaio-offline`. Adding a store there would need a
 * DB_VERSION bump, and both `writeQueue.ts` and `sw.ts` open that database
 * without ever closing the connection — an open v1 connection in a stale tab
 * would block the v2 upgrade indefinitely and silently freeze the queue. A
 * separate database at version 1 has no such hazard and needs no migration.
 */

/**
 * Owner id for a single-user self-hosted instance, where `/auth/me` is not
 * queried and there is no second user to leak to.
 */
export const SELF_HOSTED_OWNER = 'self-hosted'

/** The user a queued row belongs to; `null` means nobody is signed in. */
export type QueueOwner = string | null

export interface OwnedRow {
  /** Absent on rows queued before issue #73 was fixed — see `ownedBy`. */
  owner?: string | null
}

/**
 * Whether `row` may be replayed by the session currently signed in.
 *
 * - Nobody signed in (`owner === null`) drains nothing. A queued write is a
 *   write by *someone*; with no session there is no one to attribute it to.
 * - Rows with no owner predate this fix. Their author is unknowable, so they
 *   replay only on a self-hosted instance, where there is exactly one possible
 *   author. On a multi-user deployment they are never replayed — losing one
 *   device's pre-upgrade offline work beats executing it as the wrong user.
 *   They are left on disk rather than deleted so they stay recoverable.
 */
export function ownedBy(row: OwnedRow, owner: QueueOwner): boolean {
  if (owner === null) return false
  const rowOwner = row.owner ?? null
  if (rowOwner === null) return owner === SELF_HOSTED_OWNER
  return rowOwner === owner
}

/** The subset of `rows` the current session is allowed to replay. */
export function selectDrainable<T extends OwnedRow>(rows: T[], owner: QueueOwner): T[] {
  return rows.filter((row) => ownedBy(row, owner))
}

// ── Persistence ──────────────────────────────────────────────
// Deliberately a separate database from `studyaio-offline`; see the module
// docstring for why.

const DB_NAME = 'studyaio-session'
const STORE_NAME = 'meta'
const DB_VERSION = 1
const OWNER_KEY = 'queue-owner'

/** Fallback for non-browser contexts (SSR, unit tests without IndexedDB). */
let memoryOwner: QueueOwner = null

function hasIndexedDB(): boolean {
  return typeof indexedDB !== 'undefined' && indexedDB !== null
}

function openDB(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION)
    req.onupgradeneeded = () => {
      const db = req.result
      if (!db.objectStoreNames.contains(STORE_NAME)) {
        db.createObjectStore(STORE_NAME)
      }
    }
    req.onsuccess = () => resolve(req.result)
    req.onerror = () => reject(req.error)
  })
}

/**
 * The user the persisted offline state currently belongs to.
 *
 * Returns `null` — "drain nothing" — if the lookup fails for any reason. A
 * broken read must not open the replay gate.
 */
export async function getQueueOwner(): Promise<QueueOwner> {
  if (!hasIndexedDB()) return memoryOwner
  try {
    const db = await openDB()
    return await new Promise<QueueOwner>((resolve, reject) => {
      const tx = db.transaction(STORE_NAME, 'readonly')
      const req = tx.objectStore(STORE_NAME).get(OWNER_KEY)
      req.onsuccess = () => resolve((req.result as QueueOwner | undefined) ?? null)
      req.onerror = () => reject(req.error)
    })
  } catch (err) {
    console.warn('queueOwner: could not read the queue owner', err)
    return null
  }
}

/** Record who the persisted offline state belongs to from now on. */
export async function setQueueOwner(owner: QueueOwner): Promise<void> {
  memoryOwner = owner
  if (!hasIndexedDB()) return
  try {
    const db = await openDB()
    await new Promise<void>((resolve, reject) => {
      const tx = db.transaction(STORE_NAME, 'readwrite')
      tx.objectStore(STORE_NAME).put(owner, OWNER_KEY)
      tx.oncomplete = () => resolve()
      tx.onerror = () => reject(tx.error)
    })
  } catch (err) {
    console.warn('queueOwner: could not persist the queue owner', err)
  }
}
