import { Link } from 'react-router-dom'

export function NotFoundPage() {
  return (
    <div className="flex flex-col items-center justify-center min-h-[50vh] px-4">
      <div className="w-full max-w-md text-center">
        <div className="text-6xl font-bold text-text-faint mb-2">404</div>
        <h1 className="text-xl font-semibold text-text mb-2">
          Page not found
        </h1>
        <p className="text-text-muted mb-6">
          The page you're looking for doesn't exist or has been moved.
        </p>
        <Link
          to="/"
          className="min-h-[44px] px-6 py-2.5 bg-sage text-on-accent font-medium rounded-lg hover:bg-sage-hover transition-colors inline-flex items-center justify-center"
        >
          Go to Dashboard
        </Link>
      </div>
    </div>
  )
}
