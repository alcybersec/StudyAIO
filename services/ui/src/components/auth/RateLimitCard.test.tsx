import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { act, render, screen } from '@testing-library/react'
import { RateLimitCard } from './RateLimitCard'
import { formatCountdown } from './formatCountdown'

describe('formatCountdown', () => {
  it('formats seconds as m:ss', () => {
    expect(formatCountdown(272)).toBe('4:32')
    expect(formatCountdown(60)).toBe('1:00')
    expect(formatCountdown(9)).toBe('0:09')
  })

  it('clamps negative values to zero', () => {
    expect(formatCountdown(-5)).toBe('0:00')
  })
})

describe('RateLimitCard', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('renders the initial countdown', () => {
    render(<RateLimitCard seconds={272} />)
    expect(screen.getByRole('status')).toHaveTextContent('Too many attempts')
    expect(screen.getByRole('status')).toHaveTextContent('4:32')
  })

  it('ticks down once per second', () => {
    render(<RateLimitCard seconds={272} />)
    act(() => {
      vi.advanceTimersByTime(1000)
    })
    expect(screen.getByRole('status')).toHaveTextContent('4:31')
    act(() => {
      vi.advanceTimersByTime(31_000)
    })
    expect(screen.getByRole('status')).toHaveTextContent('4:00')
  })

  it('calls onExpire exactly once when reaching zero and stops at 0:00', () => {
    const onExpire = vi.fn()
    render(<RateLimitCard seconds={3} onExpire={onExpire} />)
    act(() => {
      vi.advanceTimersByTime(3000)
    })
    expect(screen.getByRole('status')).toHaveTextContent('0:00')
    expect(onExpire).toHaveBeenCalledTimes(1)
    act(() => {
      vi.advanceTimersByTime(5000)
    })
    expect(onExpire).toHaveBeenCalledTimes(1)
  })
})
