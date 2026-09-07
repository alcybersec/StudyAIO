import { describe, expect, it } from 'vitest'
import { SELF_HOSTED_OWNER, ownedBy, selectDrainable, type OwnedRow } from './queueOwner'

describe('ownedBy', () => {
  it('lets a user replay their own rows', () => {
    expect(ownedBy({ owner: 'user-a' }, 'user-a')).toBe(true)
  })

  it("refuses to replay another user's rows", () => {
    expect(ownedBy({ owner: 'user-a' }, 'user-b')).toBe(false)
  })

  it('replays nothing when nobody is signed in', () => {
    expect(ownedBy({ owner: 'user-a' }, null)).toBe(false)
    expect(ownedBy({ owner: undefined }, null)).toBe(false)
  })

  it('replays unowned legacy rows only on a self-hosted instance', () => {
    // Pre-fix rows have no owner. On a single-user instance there is exactly
    // one possible author; on a multi-user one there is no way to tell.
    expect(ownedBy({}, SELF_HOSTED_OWNER)).toBe(true)
    expect(ownedBy({ owner: null }, SELF_HOSTED_OWNER)).toBe(true)
    expect(ownedBy({}, 'user-a')).toBe(false)
  })

  it("does not let a self-hosted owner claim a named user's rows", () => {
    expect(ownedBy({ owner: 'user-a' }, SELF_HOSTED_OWNER)).toBe(false)
  })
})

describe('selectDrainable', () => {
  const rows: (OwnedRow & { id: number })[] = [
    { id: 1, owner: 'user-a' },
    { id: 2, owner: 'user-b' },
    { id: 3, owner: 'user-a' },
    { id: 4 },
  ]

  it("keeps only the current session's rows, in order", () => {
    expect(selectDrainable(rows, 'user-a').map((r) => r.id)).toEqual([1, 3])
    expect(selectDrainable(rows, 'user-b').map((r) => r.id)).toEqual([2])
  })

  it('keeps nothing when signed out', () => {
    expect(selectDrainable(rows, null)).toEqual([])
  })
})
