import { Suspense, useState } from 'react'
import { Link, Outlet, useLocation, useMatches } from 'react-router-dom'
import { AnimatePresence } from 'motion/react'
import { useAuth } from '../../hooks/useAuth'
import { useShortcuts } from '../../hooks/useShortcuts'
import { openCommandPalette } from '../../lib/commandPalette'
import type { AppRouteHandle } from '../../router'
import { CommandPalette } from '../CommandPalette'
import { ShortcutOverlay } from '../ShortcutOverlay'
import { ErrorBoundary } from '../ErrorBoundary'
import { DemoBanner } from '../demo/DemoBanner'
import { EmailVerificationBanner } from '../auth/EmailVerificationBanner'
import { OnboardingTour } from '../tour/OnboardingTour'
import { Toaster } from '../ui/Toast'
import { ConnectionStatus } from '../ui/ConnectionStatus'
import { SyncChip } from '../ui/SyncChip'
import { PWAUpdateNotify } from '../pwa/PWAUpdateNotify'
import { PageTransition } from '../ui/PageTransition'
import { LoadingSpinner } from '../ui/LoadingSpinner'
import { Sidebar } from './Sidebar'
import { MobileNav } from './MobileNav'

export function AppLayout() {
  const { isDemo } = useAuth()
  const location = useLocation()
  const matches = useMatches()
  const [shortcutOverlayOpen, setShortcutOverlayOpen] = useState(false)
  useShortcuts({
    onOpenPalette: openCommandPalette,
    onOpenOverlay: () => setShortcutOverlayOpen(true),
  })
  const isFullBleed = matches.some(
    (match) => (match.handle as AppRouteHandle | undefined)?.fullBleed === true,
  )

  return (
    <div className="h-screen bg-surface-0 flex flex-col overflow-hidden">
      {/* Skip to main content (accessibility) */}
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-[100] focus:px-4 focus:py-2 focus:bg-sage focus:text-on-accent focus:rounded-lg focus:text-sm focus:font-medium"
      >
        Skip to main content
      </a>

      {/* Demo account banner */}
      {isDemo && <DemoBanner />}

      {/* Unverified-email notice (password-registered users only) */}
      <EmailVerificationBanner />

      <div className="flex flex-1 min-h-0">
        {/* Desktop sidebar */}
        <Sidebar />

        {/* Main content area */}
        <div className="flex-1 flex flex-col min-w-0 min-h-0">
          {/* Mobile top header — logo only */}
          <header className="lg:hidden flex items-center h-14 px-4 bg-surface-1 border-b border-border shrink-0">
            <Link to="/" className="text-lg font-bold text-sage-fg">
              StudyAIO
            </Link>
          </header>

          {/* connectivity + sync slot */}
          <ConnectionStatus />
          <SyncChip floating />

          <main
            id="main-content"
            className={
              isFullBleed
                ? 'flex-1 flex flex-col min-h-0 pb-14 lg:pb-0'
                : 'flex-1 overflow-y-auto px-4 sm:px-6 lg:px-8 py-6 pb-20 lg:pb-6'
            }
          >
            <ErrorBoundary>
              {isFullBleed ? (
                <Suspense fallback={<LoadingSpinner size="lg" label="Loading..." />}>
                  <Outlet />
                </Suspense>
              ) : (
                <div className="w-full">
                  <AnimatePresence mode="wait">
                    <PageTransition key={location.pathname}>
                      <Suspense fallback={<LoadingSpinner size="lg" label="Loading..." />}>
                        <Outlet />
                      </Suspense>
                    </PageTransition>
                  </AnimatePresence>
                </div>
              )}
            </ErrorBoundary>
          </main>
        </div>

        {/* Mobile bottom tabs */}
        <MobileNav />

        {/* ⌘K palette + keyboard shortcut overlay */}
        <CommandPalette />
        <ShortcutOverlay open={shortcutOverlayOpen} onOpenChange={setShortcutOverlayOpen} />

        {/* Global toast notifications */}
        <Toaster />

        {/* PWA update notifications */}
        <PWAUpdateNotify />

        {/* Onboarding tour (auto-starts for demo users) */}
        <OnboardingTour />
      </div>
    </div>
  )
}
