import { Suspense } from 'react'
import { Link, Outlet, useLocation } from 'react-router-dom'
import { AnimatePresence } from 'motion/react'
import { useAuth } from '../../hooks/useAuth'
import { ErrorBoundary } from '../ErrorBoundary'
import { DemoBanner } from '../demo/DemoBanner'
import { OnboardingTour } from '../tour/OnboardingTour'
import { Toaster } from '../ui/Toast'
import { OfflineBanner } from '../ui/OfflineBanner'
import { PWAUpdateNotify } from '../pwa/PWAUpdateNotify'
import { PageTransition } from '../ui/PageTransition'
import { LoadingSpinner } from '../ui/LoadingSpinner'
import { Sidebar } from './Sidebar'
import { MobileNav } from './MobileNav'

export function AppLayout() {
  const { isDemo } = useAuth()
  const location = useLocation()
  const isFullBleed = location.pathname === '/chat' || location.pathname.startsWith('/chat/')

  return (
    <div className="h-screen bg-surface-alt flex flex-col overflow-hidden">
      {/* Skip to main content (accessibility) */}
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-[100] focus:px-4 focus:py-2 focus:bg-primary focus:text-white focus:rounded-lg focus:text-sm focus:font-medium"
      >
        Skip to main content
      </a>

      {/* Demo account banner */}
      {isDemo && <DemoBanner />}

      <div className="flex flex-1 min-h-0">
      {/* Offline status banner */}
      <OfflineBanner />

      {/* Desktop sidebar */}
      <Sidebar />

      {/* Main content area */}
      <div className="flex-1 flex flex-col min-w-0 min-h-0">
        {/* Mobile top header — logo only */}
        <header className="lg:hidden flex items-center h-14 px-4 bg-surface border-b border-border shrink-0">
          <Link to="/" className="text-lg font-bold text-primary">
            StudyAIO
          </Link>
        </header>

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
