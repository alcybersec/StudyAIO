import { useCallback, useContext, useMemo, useSyncExternalStore } from 'react'
import { AuthContext } from '../contexts/AuthContext'

/**
 * Per-user first-run checklist state, kept in localStorage under the user's id
 * so a shared browser does not leak one account's dismissal to the next.
 * Storage can throw (private mode, quota, disabled); the in-memory copy keeps
 * the session consistent and nothing is lost but persistence.
 */
export interface OnboardingStored {
  dismissed: boolean
  /** Set when the user re-opens the checklist from settings, so it shows even when finished. */
  reopened: boolean
  summaryRead: boolean
}

const DEFAULT_STATE: OnboardingStored = { dismissed: false, reopened: false, summaryRead: false }

export const onboardingKey = (userId: string) => `studyaio_onboarding:${userId}`

const memory = new Map<string, string>()
let listeners: Array<() => void> = []

function subscribe(listener: () => void) {
  listeners = [...listeners, listener]
  return () => {
    listeners = listeners.filter((l) => l !== listener)
  }
}

function readRaw(key: string): string | null {
  try {
    const raw = localStorage.getItem(key)
    if (raw !== null) return raw
  } catch {
    // fall through to the in-memory copy
  }
  return memory.get(key) ?? null
}

function writeRaw(key: string, value: string) {
  memory.set(key, value)
  try {
    localStorage.setItem(key, value)
  } catch {
    // not persisted; this session still sees it via `memory`
  }
  for (const l of listeners) l()
}

export function parseOnboarding(raw: string | null): OnboardingStored {
  if (!raw) return DEFAULT_STATE
  try {
    const v = JSON.parse(raw) as Partial<OnboardingStored> | null
    return {
      dismissed: v?.dismissed === true,
      reopened: v?.reopened === true,
      summaryRead: v?.summaryRead === true,
    }
  } catch {
    return DEFAULT_STATE
  }
}

/** Test seam: forget the in-memory copy. */
export function resetOnboardingMemory() {
  memory.clear()
}

export function useOnboardingState() {
  // Read the context directly: Settings renders this too, and neither should throw outside a provider.
  const userId = useContext(AuthContext)?.user?.id ?? null
  const key = userId ? onboardingKey(userId) : null

  const raw = useSyncExternalStore(
    subscribe,
    () => (key ? readRaw(key) : null),
    () => null,
  )
  const state = useMemo(() => parseOnboarding(raw), [raw])

  const update = useCallback(
    (patch: Partial<OnboardingStored>) => {
      if (!key) return
      writeRaw(key, JSON.stringify({ ...parseOnboarding(readRaw(key)), ...patch }))
    },
    [key],
  )

  return {
    ready: key !== null,
    ...state,
    dismiss: useCallback(() => update({ dismissed: true, reopened: false }), [update]),
    reopen: useCallback(() => update({ dismissed: false, reopened: true }), [update]),
    markSummaryRead: useCallback(() => update({ summaryRead: true }), [update]),
  }
}
