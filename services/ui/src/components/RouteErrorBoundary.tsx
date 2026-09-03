import { useEffect } from 'react'
import { useNavigate, useRouteError } from 'react-router-dom'
import { captureError } from '../lib/monitoring'
import { RefreshCw } from 'lucide-react'
import { Button } from './ui/Button'
import { ErrorState } from './ui/ErrorState'

const CHUNK_LOAD_PATTERN =
  /Loading chunk|Failed to fetch dynamically imported module|error loading dynamically imported module|Importing a module script failed/i

function isChunkLoadError(error: unknown): boolean {
  if (!(error instanceof Error)) return false
  return error.name === 'ChunkLoadError' || CHUNK_LOAD_PATTERN.test(error.message)
}

function errorDetail(error: unknown): string {
  if (error instanceof Error) return `${error.name}: ${error.message}`
  if (typeof error === 'object' && error !== null && 'statusText' in error) {
    const routeError = error as { status?: number; statusText?: string }
    return `${routeError.status ?? ''} ${routeError.statusText ?? ''}`.trim()
  }
  return String(error)
}

/**
 * Route-level error boundary rendered inside the shell's Outlet so a page
 * crash (or a stale chunk after a deploy) never takes down navigation.
 */
export function RouteErrorBoundary() {
  const error = useRouteError()
  const navigate = useNavigate()
  const isStaleChunk = isChunkLoadError(error)

  useEffect(() => {
    // A stale chunk means the user is on an old build, not that the app broke.
    if (!isStaleChunk) captureError(error, { boundary: 'route' })
  }, [error, isStaleChunk])

  if (isStaleChunk) {
    return (
      <div role="alert" className="max-w-lg mx-auto mt-16 px-6 text-center space-y-3">
        <p className="text-sm font-medium text-text">New version available — reload to update</p>
        <p className="text-xs text-text-muted">
          This page was updated since you last loaded the app, so its code couldn't be fetched.
        </p>
        <Button variant="primary" size="sm" onClick={() => window.location.reload()}>
          <RefreshCw size={12} aria-hidden /> Reload
        </Button>
      </div>
    )
  }

  return (
    <div className="max-w-lg mx-auto mt-16 px-6">
      <ErrorState
        title="This page hit a problem"
        detail={errorDetail(error)}
        onRetry={() => navigate(0)}
      />
    </div>
  )
}
