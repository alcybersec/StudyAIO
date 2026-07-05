import { useCheckout } from '../../hooks/useBilling'

interface UpgradePromptProps {
  resource: string
  limit: number
  period: string
  onDismiss: () => void
}

export function UpgradePrompt({ resource, limit, period, onDismiss }: UpgradePromptProps) {
  const checkout = useCheckout()

  const resourceLabels: Record<string, string> = {
    uploads: 'file uploads',
    ai_calls: 'AI requests',
    courses: 'courses',
  }

  const label = resourceLabels[resource] || resource

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-surface-1 border border-border rounded-xl shadow-xl max-w-md w-full mx-4 p-6">
        <div className="text-center">
          <div className="w-12 h-12 mx-auto mb-4 rounded-full bg-amber-soft flex items-center justify-center">
            <svg className="w-6 h-6 text-amber-fg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
          </div>

          <h3 className="text-lg font-semibold text-text mb-2">
            Upgrade to Pro
          </h3>

          <p className="text-sm text-text-muted mb-6">
            You've reached the free plan limit of {limit} {label} per {period}.
            Upgrade to Pro for unlimited access.
          </p>

          <div className="flex gap-3">
            <button
              type="button"
              onClick={onDismiss}
              className="flex-1 px-4 py-2.5 text-sm font-medium rounded-lg border border-border text-text hover:bg-surface-2 transition-colors"
            >
              Maybe later
            </button>
            <button
              type="button"
              onClick={() => checkout.mutate()}
              disabled={checkout.isPending}
              className="flex-1 px-4 py-2.5 text-sm font-medium rounded-lg bg-sage text-on-accent hover:bg-sage-hover disabled:opacity-50 transition-colors"
            >
              {checkout.isPending ? 'Loading...' : 'Upgrade'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
