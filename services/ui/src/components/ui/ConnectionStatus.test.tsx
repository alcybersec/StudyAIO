import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'

const mocks = vi.hoisted(() => ({
  isOnline: true,
  queueSize: 0,
  swPending: 0,
}))

vi.mock('../../hooks/useOnlineStatus', () => ({
  useOnlineStatus: () => mocks.isOnline,
}))

vi.mock('../../hooks/usePendingSync', () => ({
  usePendingSync: () => ({
    isOnline: mocks.isOnline,
    pendingCount: mocks.swPending,
    requestReplay: vi.fn(),
  }),
}))

vi.mock('../../lib/writeQueue', () => ({
  writeQueue: {
    subscribe: () => () => {},
    size: () => mocks.queueSize,
    flush: vi.fn().mockResolvedValue(undefined),
  },
}))

import { ConnectionStatus } from './ConnectionStatus'

describe('ConnectionStatus', () => {
  beforeEach(() => {
    mocks.isOnline = true
    mocks.queueSize = 0
    mocks.swPending = 0
  })

  it('renders nothing when online with an empty queue', () => {
    const { container } = render(<ConnectionStatus />)
    expect(container).toBeEmptyDOMElement()
  })

  it('shows the offline banner when offline', () => {
    mocks.isOnline = false
    render(<ConnectionStatus />)
    expect(screen.getByRole('status')).toHaveTextContent(/offline/i)
  })

  it('shows the queued count while offline with pending writes', () => {
    mocks.isOnline = false
    mocks.queueSize = 2
    render(<ConnectionStatus />)
    expect(screen.getByRole('status')).toHaveTextContent(/2 queued/i)
  })

  it('shows the reconnecting state when back online with queued writes', () => {
    mocks.isOnline = true
    mocks.swPending = 3
    render(<ConnectionStatus />)
    expect(screen.getByRole('status')).toHaveTextContent(/syncing 3/i)
  })
})
