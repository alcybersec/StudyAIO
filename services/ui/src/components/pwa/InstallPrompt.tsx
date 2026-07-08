import { useState, useEffect, useCallback } from 'react'

interface BeforeInstallPromptEvent extends Event {
  prompt(): Promise<void>
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>
}

const DISMISS_KEY = 'studyaio-install-dismissed'

function isStandalone() {
  return (
    window.matchMedia('(display-mode: standalone)').matches ||
    ('standalone' in navigator && (navigator as { standalone?: boolean }).standalone === true)
  )
}

function isIOS() {
  return /iPad|iPhone|iPod/.test(navigator.userAgent) && !('MSStream' in window)
}

export function InstallPrompt() {
  const [deferredPrompt, setDeferredPrompt] = useState<BeforeInstallPromptEvent | null>(null)
  const showIOSPrompt = !isStandalone() && isIOS()
  const [dismissed, setDismissed] = useState(() => {
    try {
      return localStorage.getItem(DISMISS_KEY) === 'true'
    } catch {
      return false
    }
  })

  useEffect(() => {
    if (isStandalone() || dismissed || isIOS()) return

    const handler = (e: Event) => {
      e.preventDefault()
      setDeferredPrompt(e as BeforeInstallPromptEvent)
    }

    window.addEventListener('beforeinstallprompt', handler)
    return () => window.removeEventListener('beforeinstallprompt', handler)
  }, [dismissed])

  const handleInstall = useCallback(async () => {
    if (!deferredPrompt) return
    await deferredPrompt.prompt()
    const { outcome } = await deferredPrompt.userChoice
    if (outcome === 'accepted') {
      setDeferredPrompt(null)
    }
  }, [deferredPrompt])

  const handleDismiss = useCallback(() => {
    setDismissed(true)
    setDeferredPrompt(null)
    try {
      localStorage.setItem(DISMISS_KEY, 'true')
    } catch { /* noop */ }
  }, [])

  if (dismissed || isStandalone()) return null
  if (!deferredPrompt && !showIOSPrompt) return null

  return (
    <div className="rounded-lg border border-sage/20 bg-sage-soft p-4 mt-6">
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1">
          <h3 className="text-sm font-semibold text-text">Install StudyAIO</h3>
          {showIOSPrompt ? (
            <p className="mt-1 text-sm text-text-muted">
              Tap the Share button
              <svg className="inline-block w-4 h-4 mx-1 -mt-0.5" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 8.25H7.5a2.25 2.25 0 0 0-2.25 2.25v9a2.25 2.25 0 0 0 2.25 2.25h9a2.25 2.25 0 0 0 2.25-2.25v-9a2.25 2.25 0 0 0-2.25-2.25H15m0-3-3-3m0 0-3 3m3-3V15" />
              </svg>
              then "Add to Home Screen" for quick access and offline study.
            </p>
          ) : (
            <p className="mt-1 text-sm text-text-muted">
              Add to your home screen for quick access and offline flashcard study.
            </p>
          )}
        </div>
        <button
          onClick={handleDismiss}
          className="text-text-muted hover:text-text shrink-0"
          aria-label="Dismiss install prompt"
        >
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" d="M6 18 18 6M6 6l12 12" />
          </svg>
        </button>
      </div>
      {deferredPrompt && (
        <button
          onClick={handleInstall}
          className="mt-3 rounded-md bg-sage px-4 py-2 text-sm font-medium text-on-accent hover:bg-sage-hover transition-colors"
        >
          Install App
        </button>
      )}
    </div>
  )
}
