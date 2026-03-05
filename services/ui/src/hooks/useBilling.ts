import { useMutation, useQuery } from '@tanstack/react-query'
import { billingApi } from '../api/billing'

export function useBillingOverview() {
  return useQuery({
    queryKey: ['billing'],
    queryFn: billingApi.getOverview,
  })
}

export function useCheckout() {
  return useMutation({
    mutationFn: () => {
      const successUrl = `${window.location.origin}/settings?billing=success`
      const cancelUrl = `${window.location.origin}/settings?billing=cancel`
      return billingApi.createCheckout(successUrl, cancelUrl)
    },
    onSuccess: (data) => {
      window.location.href = data.checkout_url
    },
  })
}

export function usePortal() {
  return useMutation({
    mutationFn: () => billingApi.createPortal(),
    onSuccess: (data) => {
      window.location.href = data.portal_url
    },
  })
}
