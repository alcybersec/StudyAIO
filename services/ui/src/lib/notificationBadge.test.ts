import { describe, expect, it } from 'vitest'
import { bellBadge } from './notificationBadge'

describe('bellBadge', () => {
  it('shows nothing at zero (or negative) unread', () => {
    expect(bellBadge(0)).toEqual({ kind: 'none' })
    expect(bellBadge(-3)).toEqual({ kind: 'none' })
  })

  it('shows a dot for exactly one unread', () => {
    expect(bellBadge(1)).toEqual({ kind: 'dot' })
  })

  it('shows the number from two unread', () => {
    expect(bellBadge(2)).toEqual({ kind: 'count', label: '2' })
    expect(bellBadge(9)).toEqual({ kind: 'count', label: '9' })
  })

  it('caps the number at 9+', () => {
    expect(bellBadge(10)).toEqual({ kind: 'count', label: '9+' })
    expect(bellBadge(120)).toEqual({ kind: 'count', label: '9+' })
  })
})
