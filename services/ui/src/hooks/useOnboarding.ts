import { useContext } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AuthContext } from '../contexts/AuthContext'
import { onboardingApi } from '../api/onboarding'
import type { OnboardingChecklist, OnboardingStatus } from '../types'

/** Where the pre-server version kept its dismissal, per user. */
export const legacyOnboardingKey = (userId: string) => `studyaio_onboarding:${userId}`

const onboardingQueryKey = (userId: string | null) => ['onboarding', userId] as const

function readLegacy(key: string): { dismissed: boolean } | null {
  try {
    const raw = localStorage.getItem(key)
    if (raw === null) return null
    try {
      return { dismissed: (JSON.parse(raw) as { dismissed?: unknown } | null)?.dismissed === true }
    } catch {
      return { dismissed: false }
    }
  } catch {
    return null
  }
}

function clearLegacy(key: string) {
  try {
    localStorage.removeItem(key)
  } catch {
    // nothing to clear if storage is unreachable
  }
}

/**
 * The caller's first-run status. A dismissal left in localStorage by the old
 * version is sent once as a PATCH and the key is cleared only after the server
 * accepted it, so a failed request retries rather than resurrecting the card.
 */
export function useOnboarding() {
  const userId = useContext(AuthContext)?.user?.id ?? null
  return useQuery({
    queryKey: onboardingQueryKey(userId),
    enabled: userId !== null,
    queryFn: async (): Promise<OnboardingStatus> => {
      const key = userId ? legacyOnboardingKey(userId) : null
      const legacy = key ? readLegacy(key) : null
      if (key && legacy?.dismissed) {
        const status = await onboardingApi.setChecklist('dismissed')
        clearLegacy(key)
        return status
      }
      if (key && legacy) clearLegacy(key)
      return onboardingApi.get()
    },
  })
}

/** Dismiss / pin / reset the checklist; the response replaces the cached status. */
export function useSetChecklist() {
  const queryClient = useQueryClient()
  const userId = useContext(AuthContext)?.user?.id ?? null
  return useMutation({
    mutationFn: (checklist: OnboardingChecklist) => onboardingApi.setChecklist(checklist),
    onSuccess: (status) => queryClient.setQueryData(onboardingQueryKey(userId), status),
  })
}
