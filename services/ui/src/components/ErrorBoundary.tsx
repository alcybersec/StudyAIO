import { Component, type ErrorInfo, type ReactNode } from 'react'
import { Link } from 'react-router-dom'

interface ErrorBoundaryProps {
  children: ReactNode
}

interface ErrorBoundaryState {
  hasError: boolean
  error: Error | null
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('ErrorBoundary caught:', error, errorInfo)
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null })
  }

  render() {
    if (!this.state.hasError) {
      return this.props.children
    }

    return (
      <div className="flex flex-col items-center justify-center min-h-[50vh] px-4" role="alert">
        <div className="w-full max-w-md text-center">
          <div className="text-5xl mb-4">&#x26A0;</div>
          <h1 className="text-xl font-semibold text-text mb-2">
            Something went wrong
          </h1>
          <p className="text-text-muted mb-6">
            An unexpected error occurred while rendering this page.
          </p>

          {import.meta.env.DEV && this.state.error && (
            <pre className="mb-6 p-3 bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-900 rounded-lg text-left text-xs text-red-800 dark:text-red-300 overflow-auto max-h-40">
              {this.state.error.message}
              {this.state.error.stack && `\n\n${this.state.error.stack}`}
            </pre>
          )}

          <div className="flex flex-col sm:flex-row gap-3 justify-center">
            <button
              onClick={this.handleReset}
              className="min-h-[44px] px-6 py-2.5 bg-primary text-white font-medium rounded-lg hover:bg-primary/90 transition-colors"
            >
              Try again
            </button>
            <Link
              to="/"
              className="min-h-[44px] px-6 py-2.5 bg-surface-alt text-text font-medium rounded-lg hover:opacity-80 transition-colors inline-flex items-center justify-center"
            >
              Go to Dashboard
            </Link>
          </div>
        </div>
      </div>
    )
  }
}
