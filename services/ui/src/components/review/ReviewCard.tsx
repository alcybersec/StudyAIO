import { useState } from 'react'
import { Badge, Card } from '../ui'
import { SuggestionButtons } from './SuggestionButtons'
import { CustomResolutionForm } from './CustomResolutionForm'
import type { ReviewItem } from '../../types'

interface ReviewCardProps {
  item: ReviewItem
  onResolve: (reviewId: string, resolution: Record<string, unknown>) => void
  onDismiss: (reviewId: string) => void
  isResolving: boolean
  isDismissing: boolean
}

const typeVariant: Record<string, 'warning' | 'info' | 'danger' | 'default'> = {
  classification: 'warning',
  extraction: 'info',
  duplicate: 'danger',
}

export function ReviewCard({ item, onResolve, onDismiss, isResolving, isDismissing }: ReviewCardProps) {
  const [showCustom, setShowCustom] = useState(false)
  const isLoading = isResolving || isDismissing

  const payload = item.payload_json
  const filename = (payload.original_filename as string) ?? (payload.filename as string) ?? null
  const reason = (payload.reason as string) ?? (payload.message as string) ?? null
  const context = (payload.context as string) ?? (payload.excerpt as string) ?? null

  return (
    <Card>
      <div className="flex items-start justify-between gap-3 mb-4">
        <div className="flex items-center gap-2 flex-wrap">
          <Badge variant={typeVariant[item.review_type] ?? 'default'} size="md">
            {item.review_type}
          </Badge>
          {filename && (
            <span className="text-sm font-medium text-gray-700">{filename}</span>
          )}
        </div>
        <span className="text-xs text-gray-400 shrink-0">
          {new Date(item.created_at).toLocaleDateString()}
        </span>
      </div>

      {reason && (
        <p className="text-sm text-gray-600 mb-3">{reason}</p>
      )}

      {context && (
        <details className="mb-4">
          <summary className="text-xs text-gray-500 cursor-pointer hover:text-gray-700">
            Show context
          </summary>
          <pre className="mt-2 text-xs bg-gray-50 rounded-lg p-3 overflow-auto max-h-32 text-gray-600">
            {context}
          </pre>
        </details>
      )}

      {/* Resolved state */}
      {item.status === 'resolved' && item.resolution_json && (
        <div className="bg-emerald-50 rounded-lg p-3 mb-3">
          <p className="text-xs font-medium text-emerald-700 mb-1">Resolved</p>
          <pre className="text-xs text-emerald-600 overflow-auto">
            {JSON.stringify(item.resolution_json, null, 2)}
          </pre>
        </div>
      )}

      {item.status === 'dismissed' && (
        <div className="bg-gray-50 rounded-lg p-3 mb-3">
          <p className="text-xs text-gray-500">Dismissed</p>
        </div>
      )}

      {/* Action area — only for pending */}
      {item.status === 'pending' && (
        <div className="space-y-4 pt-3 border-t border-gray-100">
          <SuggestionButtons
            suggestions={item.suggested_values}
            onSelect={(resolution) => onResolve(item.id, resolution)}
            isLoading={isLoading}
          />

          <div className="flex items-center gap-3">
            <button
              onClick={() => setShowCustom(!showCustom)}
              className="text-xs text-gray-500 hover:text-gray-700 underline underline-offset-2 transition-colors"
            >
              {showCustom ? 'Hide custom form' : 'Enter manually'}
            </button>
            <button
              onClick={() => onDismiss(item.id)}
              disabled={isLoading}
              className="text-xs text-red-500 hover:text-red-600 disabled:opacity-50 transition-colors"
            >
              Dismiss
            </button>
          </div>

          {showCustom && (
            <CustomResolutionForm
              onSubmit={(resolution) => onResolve(item.id, resolution)}
              isLoading={isLoading}
            />
          )}
        </div>
      )}
    </Card>
  )
}
