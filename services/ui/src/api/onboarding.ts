import { api } from './client'
import type { OnboardingChecklist, OnboardingStatus } from '../types'

/** api.onboarding v1 (docs/CONTRACTS.md): server-derived first-run status plus the one stored choice. */
export const onboardingApi = {
  get: () => api.get<OnboardingStatus>('/onboarding'),
  setChecklist: (checklist: OnboardingChecklist) => api.patch<OnboardingStatus>('/onboarding', { checklist }),
}
