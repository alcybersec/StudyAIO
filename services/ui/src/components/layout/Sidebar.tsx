import { useState, type ReactNode } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { useDashboard, useCourses } from '../../hooks/useApi'
import { useAuth } from '../../hooks/useAuth'
import { ThemeToggle } from '../ui/ThemeToggle'

interface NavItem {
  path: string
  label: string
  icon: ReactNode
}

const iconClass = 'w-5 h-5'

const DashboardIcon = (
  <svg className={iconClass} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 6A2.25 2.25 0 016 3.75h2.25A2.25 2.25 0 0110.5 6v2.25a2.25 2.25 0 01-2.25 2.25H6a2.25 2.25 0 01-2.25-2.25V6zM3.75 15.75A2.25 2.25 0 016 13.5h2.25a2.25 2.25 0 012.25 2.25V18a2.25 2.25 0 01-2.25 2.25H6A2.25 2.25 0 013.75 18v-2.25zM13.5 6a2.25 2.25 0 012.25-2.25H18A2.25 2.25 0 0120.25 6v2.25A2.25 2.25 0 0118 10.5h-2.25a2.25 2.25 0 01-2.25-2.25V6zM13.5 15.75a2.25 2.25 0 012.25-2.25H18a2.25 2.25 0 012.25 2.25V18A2.25 2.25 0 0118 20.25h-2.25A2.25 2.25 0 0113.5 18v-2.25z" />
  </svg>
)

const UploadIcon = (
  <svg className={iconClass} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
  </svg>
)

const StudyIcon = (
  <svg className={iconClass} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M4.26 10.147a60.438 60.438 0 00-.491 6.347A48.627 48.627 0 0112 20.904a48.627 48.627 0 018.232-4.41 60.46 60.46 0 00-.491-6.347m-15.482 0a50.636 50.636 0 00-2.658-.813A59.906 59.906 0 0112 3.493a59.903 59.903 0 0110.399 5.84c-.896.248-1.783.52-2.658.814m-15.482 0A50.717 50.717 0 0112 13.489a50.702 50.702 0 017.74-3.342M6.75 15a.75.75 0 100-1.5.75.75 0 000 1.5zm0 0v-3.675A55.378 55.378 0 0112 8.443m-7.007 11.55A5.981 5.981 0 006.75 15.75v-1.5" />
  </svg>
)

const ChatIcon = (
  <svg className={iconClass} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M7.5 8.25h9m-9 3H12m-9.75 1.51c0 1.6 1.123 2.994 2.707 3.227 1.129.166 2.27.293 3.423.379.35.026.67.21.865.501L12 21l2.755-4.133a1.14 1.14 0 01.865-.501 48.172 48.172 0 003.423-.379c1.584-.233 2.707-1.626 2.707-3.228V6.741c0-1.602-1.123-2.995-2.707-3.228A48.394 48.394 0 0012 3c-2.392 0-4.744.175-7.043.513C3.373 3.746 2.25 5.14 2.25 6.741v6.018z" />
  </svg>
)

const QAIcon = (
  <svg className={iconClass} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M9.879 7.519c1.171-1.025 3.071-1.025 4.242 0 1.172 1.025 1.172 2.687 0 3.712-.203.179-.43.326-.67.442-.745.361-1.45.999-1.45 1.827v.75M21 12a9 9 0 11-18 0 9 9 0 0118 0zm-9 5.25h.008v.008H12v-.008z" />
  </svg>
)

const ReviewIcon = (
  <svg className={iconClass} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M11.35 3.836c-.065.21-.1.433-.1.664 0 .414.336.75.75.75h4.5a.75.75 0 00.75-.75 2.25 2.25 0 00-.1-.664m-5.8 0A2.251 2.251 0 0113.5 2.25H15c1.012 0 1.867.668 2.15 1.586m-5.8 0c-.376.023-.75.05-1.124.08C9.095 4.01 8.25 4.973 8.25 6.108V8.25m8.9-4.414c.376.023.75.05 1.124.08 1.131.094 1.976 1.057 1.976 2.192V16.5A2.25 2.25 0 0118 18.75h-2.25m-7.5-10.5H4.875c-.621 0-1.125.504-1.125 1.125v11.25c0 .621.504 1.125 1.125 1.125h9.75c.621 0 1.125-.504 1.125-1.125V18.75m-7.5-10.5h6.375c.621 0 1.125.504 1.125 1.125v9.375m-8.25-3l1.5 1.5 3-3.75" />
  </svg>
)

const AnalyticsIcon = (
  <svg className={iconClass} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z" />
  </svg>
)

const SettingsIcon = (
  <svg className={iconClass} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.325.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 011.37.49l1.296 2.247a1.125 1.125 0 01-.26 1.431l-1.003.827c-.293.241-.438.613-.43.992a7.723 7.723 0 010 .255c-.008.378.137.75.43.991l1.004.827c.424.35.534.955.26 1.43l-1.298 2.247a1.125 1.125 0 01-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.47 6.47 0 01-.22.128c-.331.183-.581.495-.644.869l-.213 1.281c-.09.543-.56.941-1.11.941h-2.594c-.55 0-1.019-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 01-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 01-1.369-.49l-1.297-2.247a1.125 1.125 0 01.26-1.431l1.004-.827c.292-.24.437-.613.43-.991a6.932 6.932 0 010-.255c.007-.38-.138-.751-.43-.992l-1.004-.827a1.125 1.125 0 01-.26-1.43l1.297-2.247a1.125 1.125 0 011.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.086.22-.128.332-.183.582-.495.644-.869l.214-1.28z" />
    <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
  </svg>
)

const CourseIcon = (
  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M12 6.042A8.967 8.967 0 006 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 016 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 016-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0018 18a8.967 8.967 0 00-6 2.292m0-14.25v14.25" />
  </svg>
)

const CollapseIcon = (
  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 19.5L8.25 12l7.5-7.5" />
  </svg>
)

const ExpandIcon = (
  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
  </svg>
)

const mainItems: NavItem[] = [
  { path: '/', label: 'Dashboard', icon: DashboardIcon },
  { path: '/upload', label: 'Upload', icon: UploadIcon },
  { path: '/study', label: 'Study', icon: StudyIcon },
  { path: '/chat', label: 'Chat', icon: ChatIcon },
]

const KnowledgeIcon = (
  <svg className={iconClass} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M7.217 10.907a2.25 2.25 0 100 2.186m0-2.186c.18.324.283.696.283 1.093s-.103.77-.283 1.093m0-2.186l9.566-5.314m-9.566 7.5l9.566 5.314m0 0a2.25 2.25 0 103.935 2.186 2.25 2.25 0 00-3.935-2.186zm0-12.814a2.25 2.25 0 103.933-2.185 2.25 2.25 0 00-3.933 2.185z" />
  </svg>
)

const AdminIcon = (
  <svg className={iconClass} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z" />
  </svg>
)

const toolItems: NavItem[] = [
  { path: '/qa', label: 'Q&A', icon: QAIcon },
  { path: '/knowledge', label: 'Knowledge', icon: KnowledgeIcon },
  { path: '/analytics', label: 'Analytics', icon: AnalyticsIcon },
  { path: '/review', label: 'Review', icon: ReviewIcon },
]

function NavSection({ label, items, collapsed, isActive, pendingCount }: {
  label: string
  items: NavItem[]
  collapsed: boolean
  isActive: (path: string) => boolean
  pendingCount?: number
}) {
  return (
    <div>
      {!collapsed && (
        <div className="px-3 py-1.5 text-[11px] font-semibold text-text-muted uppercase tracking-wider">
          {label}
        </div>
      )}
      <ul className="space-y-0.5">
        {items.map((item) => (
          <li key={item.path} className="relative">
            <Link
              to={item.path}
              data-tour={item.path === '/' ? 'dashboard' : item.path.replace('/', '')}
              aria-current={isActive(item.path) ? 'page' : undefined}
              className={`flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                isActive(item.path)
                  ? 'bg-primary/10 text-primary'
                  : 'text-text-muted hover:text-text hover:bg-surface-alt'
              }`}
              title={collapsed ? item.label : undefined}
            >
              <span className="shrink-0">{item.icon}</span>
              {!collapsed && <span>{item.label}</span>}
              {!collapsed && item.path === '/review' && (pendingCount ?? 0) > 0 && (
                <span className="ml-auto bg-primary text-white text-xs font-bold rounded-full px-1.5 py-0.5 min-w-[1.25rem] text-center">
                  {pendingCount}
                </span>
              )}
            </Link>
            {collapsed && item.path === '/review' && (pendingCount ?? 0) > 0 && (
              <span className="absolute -top-0.5 -right-0.5 bg-primary text-white text-[10px] font-bold rounded-full w-4 h-4 flex items-center justify-center">
                {(pendingCount ?? 0) > 9 ? '9+' : pendingCount}
              </span>
            )}
          </li>
        ))}
      </ul>
    </div>
  )
}

export function Sidebar() {
  const location = useLocation()
  const [collapsed, setCollapsed] = useState(false)
  const [coursesExpanded, setCoursesExpanded] = useState(true)
  const { data: dashboard } = useDashboard()
  const { data: courses } = useCourses()
  const { user, isSelfHosted, isDemo, logout } = useAuth()

  const isActive = (path: string) => {
    if (path === '/') return location.pathname === '/'
    return location.pathname.startsWith(path)
  }

  const pendingCount = dashboard?.pending_review_count ?? 0

  return (
    <aside
      className={`hidden lg:flex flex-col bg-surface border-r border-border h-screen sticky top-0 transition-all duration-200 ${
        collapsed ? 'w-16' : 'w-60'
      }`}
    >
      {/* Header */}
      <div className="flex items-center justify-between h-16 px-4 border-b border-border">
        {!collapsed && (
          <Link to="/" className="text-lg font-bold text-primary">
            StudyAIO
          </Link>
        )}
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="p-1.5 rounded-md text-text-muted hover:text-text hover:bg-surface-alt transition-colors"
          aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          {collapsed ? ExpandIcon : CollapseIcon}
        </button>
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto py-3 px-2 space-y-4">
        <NavSection label="Main" items={mainItems} collapsed={collapsed} isActive={isActive} />
        <NavSection label="Tools" items={toolItems} collapsed={collapsed} isActive={isActive} pendingCount={pendingCount} />

        {/* Courses section */}
        {!collapsed && courses && courses.length > 0 && (
          <div>
            <button
              onClick={() => setCoursesExpanded(!coursesExpanded)}
              className="flex items-center justify-between w-full px-3 py-1.5 text-[11px] font-semibold text-text-muted uppercase tracking-wider hover:text-text"
            >
              <span>Courses</span>
              <svg className={`w-3 h-3 transition-transform ${coursesExpanded ? 'rotate-90' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
              </svg>
            </button>
            {coursesExpanded && (
              <ul className="mt-1 space-y-0.5">
                {courses.map((course) => (
                  <li key={course.id}>
                    <Link
                      to={`/courses/${course.code}`}
                      aria-current={location.pathname.startsWith(`/courses/${course.code}`) ? 'page' : undefined}
                      className={`flex items-center gap-3 px-3 py-1.5 rounded-lg text-sm transition-colors ${
                        location.pathname.startsWith(`/courses/${course.code}`)
                          ? 'bg-primary/10 text-primary font-medium'
                          : 'text-text-muted hover:text-text hover:bg-surface-alt'
                      }`}
                    >
                      <span className="shrink-0">{CourseIcon}</span>
                      <span className="truncate">{course.code}</span>
                      <span className="ml-auto text-xs text-text-muted">{course.weeks_covered}w</span>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}

        {collapsed && courses && courses.length > 0 && (
          <div className="space-y-0.5">
            {courses.map((course) => (
              <Link
                key={course.id}
                to={`/courses/${course.code}`}
                className={`flex items-center justify-center px-3 py-2 rounded-lg text-xs font-bold transition-colors ${
                  location.pathname.startsWith(`/courses/${course.code}`)
                    ? 'bg-primary/10 text-primary'
                    : 'text-text-muted hover:text-text hover:bg-surface-alt'
                }`}
                title={course.code}
              >
                {course.code.slice(0, 4)}
              </Link>
            ))}
          </div>
        )}
      </nav>

      {/* Footer: Admin + Settings + Theme + User */}
      <div className="border-t border-border p-2 space-y-1">
        {/* Admin link (admin only) */}
        {user?.role === 'admin' && (
          <Link
            to="/admin"
            aria-current={isActive('/admin') ? 'page' : undefined}
            className={`flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
              isActive('/admin')
                ? 'bg-primary/10 text-primary'
                : 'text-text-muted hover:text-text hover:bg-surface-alt'
            }`}
            title={collapsed ? 'Admin' : undefined}
          >
            <span className="shrink-0">{AdminIcon}</span>
            {!collapsed && <span>Admin</span>}
          </Link>
        )}

        {/* Settings link */}
        <Link
          to="/settings"
          data-tour="settings"
          aria-current={isActive('/settings') ? 'page' : undefined}
          className={`flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
            isActive('/settings')
              ? 'bg-primary/10 text-primary'
              : 'text-text-muted hover:text-text hover:bg-surface-alt'
          }`}
          title={collapsed ? 'Settings' : undefined}
        >
          <span className="shrink-0">{SettingsIcon}</span>
          {!collapsed && <span>Settings</span>}
        </Link>

        {/* Theme toggle */}
        <div className={`flex ${collapsed ? 'justify-center' : 'px-1'}`}>
          <ThemeToggle showLabel={!collapsed} />
        </div>

        {/* User section */}
        {(isDemo || (!isSelfHosted && user)) && user && (
          <div className="pt-1 border-t border-border mt-1">
            {collapsed ? (
              <Link
                to="/profile"
                className="flex items-center justify-center p-2 rounded-lg hover:bg-surface-alt transition-colors"
                title={user.username}
              >
                {user.avatar_url ? (
                  <img src={user.avatar_url} alt="" className="w-8 h-8 rounded-full object-cover" />
                ) : (
                  <div className="w-8 h-8 rounded-full bg-primary/10 text-primary text-sm font-bold flex items-center justify-center">
                    {user.username.charAt(0).toUpperCase()}
                  </div>
                )}
              </Link>
            ) : (
              <div className="flex items-center gap-3 px-3 py-2">
                <Link to="/profile" className="shrink-0">
                  {user.avatar_url ? (
                    <img src={user.avatar_url} alt="" className="w-8 h-8 rounded-full object-cover" />
                  ) : (
                    <div className="w-8 h-8 rounded-full bg-primary/10 text-primary text-sm font-bold flex items-center justify-center">
                      {user.username.charAt(0).toUpperCase()}
                    </div>
                  )}
                </Link>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-1.5">
                    <Link to="/profile" className="block text-sm font-medium text-text truncate hover:text-primary transition-colors">
                      {user.username}
                    </Link>
                    {isDemo && (
                      <span className="shrink-0 text-[10px] font-bold uppercase px-1.5 py-0.5 rounded bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-400">
                        Demo
                      </span>
                    )}
                  </div>
                  <button onClick={() => logout()} className="text-xs text-text-muted hover:text-danger transition-colors">
                    Sign out
                  </button>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </aside>
  )
}
