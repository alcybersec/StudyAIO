import { Link, Outlet, useLocation } from 'react-router-dom'
import { Sidebar } from './Sidebar'
import { MobileNav } from './MobileNav'

const mobileNavItems = [
  { path: '/', label: 'Dashboard' },
  { path: '/upload', label: 'Upload' },
  { path: '/review', label: 'Review' },
]

export function AppLayout() {
  const location = useLocation()

  return (
    <div className="min-h-screen bg-gray-50 flex">
      {/* Desktop sidebar */}
      <Sidebar />

      {/* Main content area */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Mobile top header */}
        <header className="lg:hidden flex items-center justify-between h-14 px-4 bg-white border-b border-gray-200 sticky top-0 z-40">
          <Link to="/" className="text-lg font-bold text-primary">
            StudyAIO
          </Link>
          <nav className="flex gap-1">
            {mobileNavItems.map((item) => (
              <Link
                key={item.path}
                to={item.path}
                className={`px-2.5 py-1 rounded-md text-xs font-medium transition-colors ${
                  (item.path === '/' ? location.pathname === '/' : location.pathname.startsWith(item.path))
                    ? 'bg-primary/10 text-primary'
                    : 'text-gray-500 hover:text-gray-700'
                }`}
              >
                {item.label}
              </Link>
            ))}
          </nav>
        </header>

        <main className="flex-1 px-4 sm:px-6 lg:px-8 py-6 pb-20 lg:pb-6 max-w-6xl w-full mx-auto">
          <Outlet />
        </main>
      </div>

      {/* Mobile bottom tabs */}
      <MobileNav />
    </div>
  )
}
