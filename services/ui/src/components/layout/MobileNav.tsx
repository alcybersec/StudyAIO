import { Link, useLocation } from 'react-router-dom'
import { useDashboard } from '../../hooks/useApi'

interface NavTab {
  path: string
  label: string
  icon: string
}

const tabs: NavTab[] = [
  { path: '/', label: 'Home', icon: '\u25A6' },
  { path: '/study', label: 'Study', icon: '\u{1F4DA}' },
  { path: '/exams', label: 'Exams', icon: '\u{1F3AF}' },
  { path: '/upload', label: 'Upload', icon: '\u2191' },
  { path: '/review', label: 'Review', icon: '\u2691' },
]

export function MobileNav() {
  const location = useLocation()
  const { data: dashboard } = useDashboard()
  const pendingCount = dashboard?.pending_review_count ?? 0

  const isActive = (path: string) => {
    if (path === '/') return location.pathname === '/'
    return location.pathname.startsWith(path)
  }

  return (
    <nav className="lg:hidden fixed bottom-0 inset-x-0 bg-white border-t border-gray-200 z-50 safe-area-pb">
      <div className="flex items-center justify-around h-14">
        {tabs.map((tab) => (
          <Link
            key={tab.path}
            to={tab.path}
            className={`relative flex flex-col items-center justify-center gap-0.5 w-full h-full text-xs transition-colors ${
              isActive(tab.path) ? 'text-primary font-medium' : 'text-gray-500'
            }`}
          >
            <span className="text-lg">{tab.icon}</span>
            <span>{tab.label}</span>
            {tab.path === '/review' && pendingCount > 0 && (
              <span className="absolute top-1 right-1/4 bg-primary text-white text-[10px] font-bold rounded-full w-4 h-4 flex items-center justify-center">
                {pendingCount > 9 ? '9+' : pendingCount}
              </span>
            )}
          </Link>
        ))}
      </div>
    </nav>
  )
}
