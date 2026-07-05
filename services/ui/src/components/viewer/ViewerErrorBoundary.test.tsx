import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { ViewerErrorBoundary } from './ViewerErrorBoundary'

function Bomb(): never {
  throw new Error('pdf worker exploded')
}

describe('ViewerErrorBoundary', () => {
  beforeEach(() => {
    // React logs caught render errors — keep test output clean
    vi.spyOn(console, 'error').mockImplementation(() => {})
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('renders children when nothing throws', () => {
    render(
      <ViewerErrorBoundary>
        <p>viewer body</p>
      </ViewerErrorBoundary>,
    )
    expect(screen.getByText('viewer body')).toBeInTheDocument()
  })

  it('contains a crash to an ErrorState instead of propagating', () => {
    render(
      <div>
        <p>summary tabs</p>
        <ViewerErrorBoundary>
          <Bomb />
        </ViewerErrorBoundary>
      </div>,
    )
    // sibling content survives; the viewer region shows its error state
    expect(screen.getByText('summary tabs')).toBeInTheDocument()
    expect(screen.getByRole('alert')).toHaveTextContent('The original file viewer failed')
  })
})
