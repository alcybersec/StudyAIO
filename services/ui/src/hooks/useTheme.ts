import { useCallback, useEffect, useSyncExternalStore } from 'react'

export type Theme = 'light' | 'dark' | 'system'

const STORAGE_KEY = 'studyaio-theme'

function getStoredTheme(): Theme {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (stored === 'light' || stored === 'dark' || stored === 'system') return stored
  } catch { /* SSR / privacy mode */ }
  return 'system'
}

function getResolvedTheme(theme: Theme): 'light' | 'dark' {
  if (theme !== 'system') return theme
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

function applyTheme(theme: Theme) {
  const resolved = getResolvedTheme(theme)
  document.documentElement.classList.toggle('dark', resolved === 'dark')
}

// Tiny external store so all consumers share one value
let currentTheme: Theme = getStoredTheme()
const listeners = new Set<() => void>()

// OS-preference listener lives with the store: attached when the first
// consumer subscribes, detached when the last one unsubscribes (no leak).
// The MediaQueryList is cached — browsers may return a fresh object per
// matchMedia() call, and removeEventListener must target the same instance.
let mediaQuery: MediaQueryList | null = null
function getMediaQuery(): MediaQueryList {
  if (!mediaQuery) mediaQuery = window.matchMedia('(prefers-color-scheme: dark)')
  return mediaQuery
}

function handleMediaChange() {
  if (currentTheme === 'system') applyTheme('system')
}

function subscribe(cb: () => void) {
  if (listeners.size === 0) {
    getMediaQuery().addEventListener('change', handleMediaChange)
  }
  listeners.add(cb)
  return () => {
    listeners.delete(cb)
    if (listeners.size === 0) {
      getMediaQuery().removeEventListener('change', handleMediaChange)
    }
  }
}
function getSnapshot() { return currentTheme }

function setTheme(next: Theme) {
  currentTheme = next
  try { localStorage.setItem(STORAGE_KEY, next) } catch { /* noop */ }
  applyTheme(next)
  listeners.forEach(cb => cb())
}

// Apply on load
if (typeof window !== 'undefined') {
  applyTheme(currentTheme)
}

export function useTheme() {
  const theme = useSyncExternalStore(subscribe, getSnapshot)

  const resolved = getResolvedTheme(theme)

  const toggle = useCallback(() => {
    const order: Theme[] = ['light', 'dark', 'system']
    const idx = order.indexOf(theme)
    setTheme(order[(idx + 1) % order.length])
  }, [theme])

  useEffect(() => { applyTheme(theme) }, [theme])

  return { theme, resolved, setTheme, toggle } as const
}
