import { Component, type ErrorInfo, type ReactNode } from 'react'
import { ErrorState } from '../ui'

interface ViewerErrorBoundaryProps {
  children: ReactNode
}

interface ViewerErrorBoundaryState {
  error: Error | null
}

/**
 * Region-scoped boundary so a viewer crash never takes the summary tabs down
 * with it — the panel swaps to an ErrorState while the rest of the week page
 * keeps working.
 */
export class ViewerErrorBoundary extends Component<ViewerErrorBoundaryProps, ViewerErrorBoundaryState> {
  state: ViewerErrorBoundaryState = { error: null }

  static getDerivedStateFromError(error: Error): ViewerErrorBoundaryState {
    return { error }
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('ViewerErrorBoundary caught:', error, errorInfo)
  }

  handleRetry = () => {
    this.setState({ error: null })
  }

  render() {
    if (this.state.error) {
      return (
        <div className="p-4 h-full bg-surface-0">
          <ErrorState
            title="The original file viewer failed"
            detail={this.state.error.message}
            onRetry={this.handleRetry}
          />
        </div>
      )
    }
    return this.props.children
  }
}
