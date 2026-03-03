import { useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { useDashboard, useCourses } from '../../hooks/useApi'

interface NavItem {
  path: string
  label: string
  icon: string
}

const mainNavItems: NavItem[] = [
  { path: '/', label: 'Dashboard', icon: '\u25A6' },
  { path: '/upload', label: 'Upload', icon: '\u2191' },
  { path: '/study', label: 'Study', icon: '\u{1F4DA}' },
  { path: '/timed-study', label: 'Timed Study', icon: '\u23F1' },
  { path: '/exams', label: 'Exams', icon: '\u{1F3AF}' },
  { path: '/qa', label: 'Q&A', icon: '?' },
  { path: '/review', label: 'Review', icon: '\u2691' },
  { path: '/settings', label: 'Settings', icon: '\u2699' },
]

export function Sidebar() {
  const location = useLocation()
  const [collapsed, setCollapsed] = useState(false)
  const [coursesExpanded, setCoursesExpanded] = useState(true)
  const { data: dashboard } = useDashboard()
  const { data: courses } = useCourses()

  const isActive = (path: string) => {
    if (path === '/') return location.pathname === '/'
    return location.pathname.startsWith(path)
  }

  const pendingCount = dashboard?.pending_review_count ?? 0

  return (
    <aside
      className={`hidden lg:flex flex-col bg-white border-r border-gray-200 h-screen sticky top-0 transition-all duration-200 ${
        collapsed ? 'w-16' : 'w-60'
      }`}
    >
      {/* Header */}
      <div className="flex items-center justify-between h-16 px-4 border-b border-gray-100">
        {!collapsed && (
          <Link to="/" className="text-lg font-bold text-primary">
            StudyAIO
          </Link>
        )}
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="p-1.5 rounded-md text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors"
          title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          {collapsed ? '\u276F' : '\u276E'}
        </button>
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto py-3 px-2">
        <ul className="space-y-0.5">
          {mainNavItems.map((item) => (
            <li key={item.path}>
              <Link
                to={item.path}
                className={`flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                  isActive(item.path)
                    ? 'bg-primary/10 text-primary'
                    : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'
                }`}
                title={collapsed ? item.label : undefined}
              >
                <span className="text-base shrink-0 w-5 text-center">{item.icon}</span>
                {!collapsed && <span>{item.label}</span>}
                {!collapsed && item.path === '/review' && pendingCount > 0 && (
                  <span className="ml-auto bg-primary text-white text-xs font-bold rounded-full px-1.5 py-0.5 min-w-[1.25rem] text-center">
                    {pendingCount}
                  </span>
                )}
                {collapsed && item.path === '/review' && pendingCount > 0 && (
                  <span className="absolute left-9 top-0 bg-primary text-white text-[10px] font-bold rounded-full w-4 h-4 flex items-center justify-center">
                    {pendingCount > 9 ? '9+' : pendingCount}
                  </span>
                )}
              </Link>
            </li>
          ))}
        </ul>

        {/* Courses section */}
        {!collapsed && courses && courses.length > 0 && (
          <div className="mt-5">
            <button
              onClick={() => setCoursesExpanded(!coursesExpanded)}
              className="flex items-center justify-between w-full px-3 py-1.5 text-xs font-semibold text-gray-400 uppercase tracking-wider hover:text-gray-600"
            >
              <span>Courses</span>
              <span className="text-[10px]">{coursesExpanded ? '\u25BC' : '\u25B6'}</span>
            </button>
            {coursesExpanded && (
              <ul className="mt-1 space-y-0.5">
                {courses.map((course) => (
                  <li key={course.id}>
                    <Link
                      to={`/courses/${course.code}`}
                      className={`flex items-center gap-3 px-3 py-1.5 rounded-lg text-sm transition-colors ${
                        location.pathname.startsWith(`/courses/${course.code}`)
                          ? 'bg-primary/10 text-primary font-medium'
                          : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'
                      }`}
                    >
                      <span className="text-base shrink-0 w-5 text-center">{'\u{1F4D6}'}</span>
                      <span className="truncate">{course.code}</span>
                      <span className="ml-auto text-xs text-gray-400">{course.weeks_covered}w</span>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}

        {collapsed && courses && courses.length > 0 && (
          <div className="mt-5 space-y-0.5">
            {courses.map((course) => (
              <Link
                key={course.id}
                to={`/courses/${course.code}`}
                className={`flex items-center justify-center px-3 py-2 rounded-lg text-xs font-bold transition-colors ${
                  location.pathname.startsWith(`/courses/${course.code}`)
                    ? 'bg-primary/10 text-primary'
                    : 'text-gray-500 hover:text-gray-900 hover:bg-gray-50'
                }`}
                title={course.code}
              >
                {course.code.slice(0, 4)}
              </Link>
            ))}
          </div>
        )}
      </nav>
    </aside>
  )
}
