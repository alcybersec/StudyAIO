import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react'
import { setQuotaExceededHandler } from '../api/client'
import { UpgradePrompt } from '../components/billing/UpgradePrompt'
import type { QuotaError } from '../types'

interface QuotaContextValue {
  showUpgradePrompt: (error: QuotaError) => void
}

const QuotaContext = createContext<QuotaContextValue | null>(null)

export function QuotaProvider({ children }: { children: ReactNode }) {
  const [quotaError, setQuotaError] = useState<QuotaError | null>(null)

  const showUpgradePrompt = useCallback((error: QuotaError) => {
    setQuotaError(error)
  }, [])

  // Register global 402 handler so API client can trigger upgrade prompt
  useEffect(() => {
    setQuotaExceededHandler((error) => {
      setQuotaError({ detail: '', ...error })
    })
    return () => setQuotaExceededHandler(null)
  }, [])

  return (
    <QuotaContext.Provider value={{ showUpgradePrompt }}>
      {children}
      {quotaError && (
        <UpgradePrompt
          resource={quotaError.resource}
          limit={quotaError.limit}
          period={quotaError.period}
          onDismiss={() => setQuotaError(null)}
        />
      )}
    </QuotaContext.Provider>
  )
}

export function useQuota(): QuotaContextValue {
  const ctx = useContext(QuotaContext)
  if (!ctx) {
    throw new Error('useQuota must be used within a QuotaProvider')
  }
  return ctx
}
