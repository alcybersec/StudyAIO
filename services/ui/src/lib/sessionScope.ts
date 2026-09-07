/**
 * Keeps everything the browser persists on behalf of a signed-in user tied to
 * that user, and tears it down when the identity changes (issue #73).
 *
 * `reconcileSession` is deliberately driven by *who is signed in*, not by the
 * logout button. A session that expires or is revoked never reaches
 * `logout()`, and that is the common case — a user closes the tab, the refresh
 * token lapses, the next person signs in on the same profile. Reacting to the
 * identity covers logout, expiry, revocation and a straight A→B switch with
 * one code path.
 */

import { readQueueOwner, setQueueOwner, type QueueOwner } from './queueOwner'

/**
 * Workbox caches that hold responses scoped to one user, and so must not
 * survive an identity change.
 *
 * `extraction-images` is listed even though the route that would populate it
 * is currently shadowed and dead (see the comment in `sw.ts`). If that
 * ordering is ever changed the cache becomes live, and it must already be
 * purged here — a 7-day CacheFirst cache of another user's lecture images is
 * the worst version of this bug.
 *
 * Not listed, deliberately: `navigation` (the SPA shell, identical for every
 * user) and the workbox precache (static build assets — deleting it breaks
 * the app offline for no benefit).
 */
export const PER_USER_CACHES = ['api-general', 'study-api', 'extraction-images']

/**
 * Delete the caches holding per-user API responses. Returns the names actually
 * deleted. Never throws: a browser with the Cache API unavailable or blocked
 * (private mode, tests) must not break sign-out.
 */
export async function clearApiCaches(
  cacheStorage: CacheStorage | undefined = typeof caches !== 'undefined' ? caches : undefined,
): Promise<string[]> {
  if (!cacheStorage) return []
  const deleted: string[] = []
  for (const name of PER_USER_CACHES) {
    try {
      if (await cacheStorage.delete(name)) deleted.push(name)
    } catch (err) {
      console.warn(`sessionScope: could not delete cache ${name}`, err)
    }
  }
  return deleted
}

export interface ReconcileDeps {
  /** `undefined` = no owner has ever been recorded in this browser profile. */
  getOwner?: () => Promise<QueueOwner | undefined>
  setOwner?: (owner: QueueOwner) => Promise<void>
  clearCaches?: () => Promise<unknown>
  /**
   * Drop in-memory (react-query) state belonging to the previous identity.
   *
   * Called only when a *recorded* previous identity is being replaced — never
   * on a first load. See `reconcileSession`.
   */
  onIdentityChange?: (previous: QueueOwner, next: QueueOwner) => void
}

// Reconciles run one at a time. A logout immediately followed by a sign-in
// must not interleave a cache purge with the new owner being written.
let chain: Promise<unknown> = Promise.resolve()

/**
 * Bring persisted browser state in line with `identity`.
 *
 * No-ops when the identity is unchanged, so a normal page load keeps its
 * offline caches. When it has changed: per-user caches are deleted, callers
 * get a chance to drop in-memory state, and the queue owner is updated so the
 * previous user's queued writes stop being drainable.
 *
 * Resolves to `true` when a purge happened.
 */
export function reconcileSession(
  identity: QueueOwner,
  deps: ReconcileDeps = {},
): Promise<boolean> {
  const {
    getOwner = readQueueOwner,
    setOwner = setQueueOwner,
    clearCaches = clearApiCaches,
    onIdentityChange,
  } = deps

  const run = chain.then(async () => {
    const previous = await getOwner()
    if ((previous ?? null) === identity) return false

    // Persisted caches outlive the page, so they are purged even on a first
    // load: a profile that used the app before this fix shipped holds the
    // previous user's cached responses and carries no owner marker.
    await clearCaches()

    // In-memory state does NOT outlive the page. On a first load react-query
    // holds nothing but this page session's own data, so there is nothing to
    // purge — and purging lands mid-load, discarding the state of queries the
    // page has already settled and leaving widgets stuck. Only a recorded
    // previous identity means a real in-session switch: logout then sign-in,
    // or an expiry followed by somebody else.
    if (previous !== undefined) onIdentityChange?.(previous, identity)

    await setOwner(identity)
    return true
  })

  // Keep the chain alive even if this reconcile rejects.
  chain = run.catch(() => undefined)
  return run
}

/** Test hook: forget the in-flight reconcile chain. */
export function resetReconcileChain() {
  chain = Promise.resolve()
}
