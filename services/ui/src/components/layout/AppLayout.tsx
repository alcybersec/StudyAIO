import { Link, Outlet } from 'react-router-dom'
import { ErrorBoundary } from '../ErrorBoundary'
import { Toaster } from '../ui/Toast'
import { Sidebar } from './Sidebar'
import { MobileNav } from './MobileNav'

export function AppLayout() {
  return (
    <div className="min-h-screen bg-surface-alt flex">
      {/* Desktop sidebar */}
      <Sidebar />

      {/* Main content area */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Mobile top header — logo only */}
        <header className="lg:hidden flex items-center h-14 px-4 bg-surface border-b border-border sticky top-0 z-40">
          <Link to="/" className="text-lg font-bold text-primary">
            StudyAIO
          </Link>
        </header>

        <main className="flex-1 px-4 sm:px-6 lg:px-8 py-6 pb-20 lg:pb-6 max-w-6xl w-full mx-auto">
          <ErrorBoundary>
            <Outlet />
          </ErrorBoundary>
        </main>
      </div>

      {/* Mobile bottom tabs */}
      <MobileNav />

      {/* Global toast notifications */}
      <Toaster />
    </div>
  )
}
