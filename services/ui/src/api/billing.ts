import { api } from './client'
import type { BillingOverview, CheckoutResponse, PortalResponse } from '../types'

export const billingApi = {
  getOverview: () => api.get<BillingOverview>('/billing/subscription'),

  createCheckout: (successUrl: string, cancelUrl: string) =>
    api.post<CheckoutResponse>('/billing/checkout', {
      success_url: successUrl,
      cancel_url: cancelUrl,
    }),

  createPortal: () => api.post<PortalResponse>('/billing/portal'),
}
