import { beforeEach, describe, expect, it, vi } from 'vitest'
import {
  PER_USER_CACHES,
  clearApiCaches,
  reconcileSession,
  resetReconcileChain,
} from './sessionScope'
import type { QueueOwner } from './queueOwner'

/** Minimal CacheStorage double — only `delete`/`keys` are exercised. */
function createCacheStorage(existing: string[]) {
  const names = new Set(existing)
  return {
    names,
    stub: {
      async delete(name: string) {
        return names.delete(name)
      },
      async keys() {
        return [...names]
      },
    } as unknown as CacheStorage,
  }
}

describe('clearApiCaches', () => {
  it('deletes every cache holding per-user responses', async () => {
    // Named literally, not derived from PER_USER_CACHES: dropping an entry
    // from that list is exactly the regression this has to catch.
    // `extraction-images` in particular — the CacheFirst route feeding it is
    // dead today, but it is one route reorder away from being a 7-day,
    // network-free cache of another user's lecture images (see sw.ts).
    const expected = ['api-general', 'study-api', 'extraction-images']
    expect([...PER_USER_CACHES].sort()).toEqual([...expected].sort())

    const { names, stub } = createCacheStorage(expected)
    const deleted = await clearApiCaches(stub)
    expect(deleted.sort()).toEqual([...expected].sort())
    expect(names.size).toBe(0)
  })

  it('leaves the app shell and precache alone', async () => {
    // Deleting these would break the PWA offline for no privacy benefit:
    // navigation is index.html, identical for every user, and the precache is
    // build output.
    const { names, stub } = createCacheStorage([
      'api-general',
      'navigation',
      'workbox-precache-v2-https://studyaio.example/',
    ])
    await clearApiCaches(stub)
    expect([...names].sort()).toEqual([
      'navigation',
      'workbox-precache-v2-https://studyaio.example/',
    ])
  })

  it('survives a Cache API that throws, and one that is missing', async () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {})
    const throwing = {
      delete: () => Promise.reject(new Error('blocked')),
    } as unknown as CacheStorage
    await expect(clearApiCaches(throwing)).resolves.toEqual([])
    expect(warn).toHaveBeenCalled()
    await expect(clearApiCaches(undefined)).resolves.toEqual([])
  })
})

describe('reconcileSession', () => {
  let owner: QueueOwner
  let clearCaches: ReturnType<typeof vi.fn>
  let onIdentityChange: ReturnType<typeof vi.fn>

  const deps = () => ({
    getOwner: async () => owner,
    setOwner: async (next: QueueOwner) => {
      owner = next
    },
    clearCaches: clearCaches as unknown as () => Promise<unknown>,
    onIdentityChange: onIdentityChange as unknown as (
      previous: QueueOwner,
      next: QueueOwner,
    ) => void,
  })

  beforeEach(() => {
    resetReconcileChain()
    owner = null
    clearCaches = vi.fn(async () => [])
    onIdentityChange = vi.fn()
  })

  it('purges caches and reassigns the queue when a user logs out', async () => {
    owner = 'user-a'
    await expect(reconcileSession(null, deps())).resolves.toBe(true)
    expect(clearCaches).toHaveBeenCalledTimes(1)
    expect(onIdentityChange).toHaveBeenCalledWith('user-a', null)
    expect(owner).toBeNull()
  })

  it('purges when the session expires and someone else signs in', async () => {
    // No logout ever happens here: user A's cookie lapses, user B signs in.
    owner = 'user-a'
    await expect(reconcileSession('user-b', deps())).resolves.toBe(true)
    expect(clearCaches).toHaveBeenCalledTimes(1)
    expect(owner).toBe('user-b')
  })

  it('does nothing on a plain page load by the same user', async () => {
    // The offline cache has to survive reloads, or the PWA is pointless.
    owner = 'user-a'
    await expect(reconcileSession('user-a', deps())).resolves.toBe(false)
    expect(clearCaches).not.toHaveBeenCalled()
    expect(onIdentityChange).not.toHaveBeenCalled()
  })

  it('purges once when logout and the identity effect both fire', async () => {
    owner = 'user-a'
    const [first, second] = await Promise.all([
      reconcileSession(null, deps()),
      reconcileSession(null, deps()),
    ])
    expect([first, second]).toEqual([true, false])
    expect(clearCaches).toHaveBeenCalledTimes(1)
  })

  it('serialises a logout immediately followed by a sign-in', async () => {
    owner = 'user-a'
    await Promise.all([
      reconcileSession(null, deps()),
      reconcileSession('user-b', deps()),
    ])
    expect(owner).toBe('user-b')
    expect(clearCaches).toHaveBeenCalledTimes(2)
  })
})
