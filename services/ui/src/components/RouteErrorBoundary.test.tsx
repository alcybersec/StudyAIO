import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { Outlet, RouterProvider, createMemoryRouter } from 'react-router-dom'
import { RouteErrorBoundary } from './RouteErrorBoundary'

function Shell() {
  return (
    <div>
      <nav>App shell nav</nav>
      <Outlet />
    </div>
  )
}

function Boom(): never {
  throw new Error('render exploded')
}

function ChunkBoom(): never {
  const err = new Error('Loading chunk 42 failed')
  err.name = 'ChunkLoadError'
  throw err
}

function renderWithThrowingRoute(element: React.ReactElement) {
  const router = createMemoryRouter([
    {
      element: <Shell />,
      children: [
        {
          errorElement: <RouteErrorBoundary />,
          children: [{ path: '/', element }],
        },
      ],
    },
  ])
  return render(<RouterProvider router={router} />)
}

describe('RouteErrorBoundary', () => {
  beforeEach(() => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('renders the error boundary while the shell nav stays visible', async () => {
    renderWithThrowingRoute(<Boom />)
    expect(await screen.findByRole('alert')).toBeInTheDocument()
    expect(screen.getByText('App shell nav')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument()
  })

  it('offers the error detail behind an expander', async () => {
    renderWithThrowingRoute(<Boom />)
    expect(await screen.findByText(/render exploded/)).toBeInTheDocument()
  })

  it('renders a reload prompt for chunk-load errors', async () => {
    renderWithThrowingRoute(<ChunkBoom />)
    expect(await screen.findByText(/new version available/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /reload/i })).toBeInTheDocument()
    expect(screen.getByText('App shell nav')).toBeInTheDocument()
  })

  it('treats "Loading chunk" messages without the ChunkLoadError name as chunk errors', async () => {
    function MessageOnlyChunkBoom(): never {
      throw new Error('Failed to fetch dynamically imported module: /assets/Page.js')
    }
    renderWithThrowingRoute(<MessageOnlyChunkBoom />)
    expect(await screen.findByText(/new version available/i)).toBeInTheDocument()
  })
})
