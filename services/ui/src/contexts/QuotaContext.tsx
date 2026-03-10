import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react'
import { setQuotaExceededHandler, setDemoRestrictionHandler } from '../api/client'
import { UpgradePrompt } from '../components/billing/UpgradePrompt'
import { UpgradeCTA } from '../components/demo/UpgradeCTA'
import type { QuotaError } from '../types'

interface QuotaContextValue {
  showUpgradePrompt: (error: QuotaError) => void
}

const QuotaContext = createContext<QuotaContextValue | null>(null)

export function QuotaProvider({ children }: { children: ReactNode }) {
  const [quotaError, setQuotaError] = useState<QuotaError | null>(null)
  const [demoBlocked, setDemoBlocked] = useState(false)

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

  // Register global 403 demo restriction handler
  useEffect(() => {
    setDemoRestrictionHandler(() => {
      setDemoBlocked(true)
    })
    return () => setDemoRestrictionHandler(null)
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
      <UpgradeCTA open={demoBlocked} onDismiss={() => setDemoBlocked(false)} />
    </QuotaContext.Provider>
  )
}

// eslint-disable-next-line react-refresh/only-export-components
export function useQuota(): QuotaContextValue {
  const ctx = useContext(QuotaContext)
  if (!ctx) {
    throw new Error('useQuota must be used within a QuotaProvider')
  }
  return ctx
}
