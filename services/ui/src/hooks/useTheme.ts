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

function subscribe(cb: () => void) {
  listeners.add(cb)
  return () => { listeners.delete(cb) }
}
function getSnapshot() { return currentTheme }

function setTheme(next: Theme) {
  currentTheme = next
  try { localStorage.setItem(STORAGE_KEY, next) } catch { /* noop */ }
  applyTheme(next)
  listeners.forEach(cb => cb())
}

// Apply on load + listen to OS changes
if (typeof window !== 'undefined') {
  applyTheme(currentTheme)
  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
    if (currentTheme === 'system') applyTheme('system')
  })
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
