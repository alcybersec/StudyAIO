import { createContext, useContext } from 'react'

export interface ConsentControls {
  /**
   * Opens the AI-processing disclosure and resolves with the answer (true once
   * recorded). The one dialog the provider owns; callers never render their own.
   */
  requestConsent: () => Promise<boolean>
}

export const ConsentContext = createContext<ConsentControls | null>(null)

/** Outside a provider there is nothing to ask, so the request resolves as agreed. */
const NO_PROVIDER: ConsentControls = { requestConsent: () => Promise.resolve(true) }

export function useConsent(): ConsentControls {
  return useContext(ConsentContext) ?? NO_PROVIDER
}
