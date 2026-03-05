import { useAuth } from './useAuth'

const PRO_FEATURES = ['knowledge_graph', 'calendar', 'full_analytics', 'unlimited_uploads', 'unlimited_ai']

export function usePlan() {
  const { user, isSelfHosted: selfHosted } = useAuth()

  const isSelfHosted = selfHosted
  const plan = isSelfHosted ? 'pro' : (user?.tier ?? 'free')

  return {
    plan,
    isSelfHosted,
    isPro: plan === 'pro',
    isFree: plan === 'free',
    isProFeature: (feature: string) => PRO_FEATURES.includes(feature) && plan !== 'pro',
    canUpgrade: !isSelfHosted && plan === 'free',
  }
}
