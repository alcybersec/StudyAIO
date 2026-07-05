import { useState, type ComponentType, type ReactNode } from 'react'
import { Link, useLocation } from 'react-router-dom'
import {
  BarChart3,
  Bell,
  ChevronRight,
  GraduationCap,
  Home,
  Inbox,
  Library,
  LogOut,
  MessageSquare,
  Network,
  PanelLeftClose,
  PanelLeftOpen,
  Search,
  Settings,
  ShieldCheck,
  Trophy,
  Upload,
  User as UserIcon,
} from 'lucide-react'
import { useDashboard, useCourses } from '../../hooks/useApi'
import { useAuth } from '../../hooks/useAuth'
import { useUnreadCount } from '../../hooks/useNotificationInbox'
import { openCommandPalette } from '../../lib/commandPalette'
import { bellBadge } from '../../lib/notificationBadge'
import { NotificationCenter } from '../notifications/NotificationCenter'
import { Badge } from '../ui/Badge'
import { Kbd } from '../ui/Kbd'
import { Sheet } from '../ui/Sheet'
import { ThemeToggle } from '../ui/ThemeToggle'
import { Tooltip } from '../ui/Tooltip'

const COLLAPSE_KEY = 'studyaio-sidebar-collapsed'

function getStoredCollapsed(): boolean {
  try {
    return localStorage.getItem(COLLAPSE_KEY) === 'true'
  } catch {
    return false
  }
}

interface NavItemProps {
  to: string
  icon: ComponentType<{ size?: number | string; strokeWidth?: number | string; className?: string }>
  label: string
  active: boolean
  collapsed: boolean
  badge?: number
  indent?: boolean
  tour?: string
}

function NavItem({ to, icon: Icon, label, active, collapsed, badge, indent, tour }: NavItemProps) {
  const link = (
    <Link
      to={to}
      data-tour={tour}
      aria-current={active ? 'page' : undefined}
      className={`w-full flex items-center gap-2.5 px-2.5 py-1.5 rounded-lg text-[13px] transition-colors ${
        active ? 'bg-surface-2 text-text font-medium' : 'text-text-muted hover:text-text hover:bg-surface-2/60'
      } ${indent && !collapsed ? 'pl-8' : ''} ${collapsed ? 'justify-center' : ''}`}
    >
      <Icon size={15} strokeWidth={1.8} className={`shrink-0 ${active ? 'text-sage-fg' : 'text-text-faint'}`} />
      {!collapsed && <span className="truncate">{label}</span>}
      {!collapsed && badge != null && badge > 0 && (
        <span className="ml-auto">
          <Badge variant="warning">{badge > 9 ? '9+' : badge}</Badge>
        </span>
      )}
    </Link>
  )
  if (collapsed) {
    return (
      <Tooltip content={label} side="right">
        {link}
      </Tooltip>
    )
  }
  return link
}

function GroupLabel({ children, collapsed }: { children: ReactNode; collapsed: boolean }) {
  if (collapsed) return <div className="h-px bg-border mx-2 my-1" aria-hidden />
  return (
    <div className="text-[9px] font-mono uppercase tracking-[0.14em] text-text-faint px-2.5 mb-1">
      {children}
    </div>
  )
}

export function Sidebar() {
  const location = useLocation()
  const [collapsed, setCollapsed] = useState(getStoredCollapsed)
  const [coursesExpanded, setCoursesExpanded] = useState(true)
  const [notificationsOpen, setNotificationsOpen] = useState(false)
  const { data: dashboard } = useDashboard()
  const { data: courses } = useCourses()
  const { user, isSelfHosted, isDemo, logout } = useAuth()

  const isActive = (path: string) =>
    path === '/' ? location.pathname === '/' : location.pathname.startsWith(path)

  const pendingCount = dashboard?.pending_review_count ?? 0
  const { data: unreadCount = 0 } = useUnreadCount()
  const badge = bellBadge(unreadCount)

  const toggleCollapsed = () => {
    const next = !collapsed
    setCollapsed(next)
    try {
      localStorage.setItem(COLLAPSE_KEY, String(next))
    } catch {
      /* private mode */
    }
  }

  const item = (props: Omit<NavItemProps, 'active' | 'collapsed'>) => (
    <NavItem {...props} active={isActive(props.to)} collapsed={collapsed} />
  )

  return (
    <aside
      className={`hidden lg:flex flex-col bg-surface-1 border-r border-border h-screen sticky top-0 transition-all duration-200 ${
        collapsed ? 'w-16' : 'w-60'
      }`}
    >
      {/* Header: logo + bell + collapse */}
      <div className={`flex items-center h-14 border-b border-border shrink-0 ${collapsed ? 'flex-col justify-center gap-1 h-auto py-2 px-2' : 'justify-between px-3.5'}`}>
        {!collapsed && (
          <Link to="/" className="flex items-center gap-2" aria-label="StudyAIO home">
            <span className="w-6 h-6 rounded-md bg-sage flex items-center justify-center text-on-accent text-xs font-bold">
              S
            </span>
            <span className="text-sm font-bold tracking-tight text-text">StudyAIO</span>
          </Link>
        )}
        <div className={`flex items-center ${collapsed ? 'flex-col gap-1' : 'gap-0.5'}`}>
          <Tooltip content="Notifications" side={collapsed ? 'right' : 'bottom'}>
            <button
              type="button"
              onClick={() => setNotificationsOpen(true)}
              aria-label={
                unreadCount > 0 ? `Notifications — ${unreadCount} unread` : 'Notifications'
              }
              className="relative p-1.5 rounded-lg text-text-muted hover:text-text hover:bg-surface-2 transition-colors cursor-pointer"
            >
              <Bell size={15} aria-hidden />
              {badge.kind === 'dot' && (
                <span className="absolute top-1 right-1 w-1.5 h-1.5 rounded-full bg-amber" aria-hidden />
              )}
              {badge.kind === 'count' && (
                <span
                  aria-hidden
                  className="absolute -top-0.5 -right-0.5 min-w-[14px] h-3.5 px-1 rounded-full bg-amber text-on-accent text-[9px] font-bold leading-none flex items-center justify-center"
                >
                  {badge.label}
                </span>
              )}
            </button>
          </Tooltip>
          <button
            type="button"
            onClick={toggleCollapsed}
            aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            className="p-1.5 rounded-lg text-text-muted hover:text-text hover:bg-surface-2 transition-colors cursor-pointer"
          >
            {collapsed ? <PanelLeftOpen size={15} aria-hidden /> : <PanelLeftClose size={15} aria-hidden />}
          </button>
        </div>
      </div>

      {/* Search affordance */}
      <div className={`pt-3 ${collapsed ? 'px-2' : 'px-3'}`}>
        <button
          type="button"
          onClick={openCommandPalette}
          aria-label="Search or jump to"
          className={`w-full flex items-center gap-2 rounded-lg border border-border text-[12px] text-text-faint hover:border-border-strong hover:text-text-muted transition-colors cursor-pointer ${
            collapsed ? 'justify-center px-0 py-1.5' : 'px-2.5 py-1.5'
          }`}
        >
          <Search size={13} aria-hidden />
          {!collapsed && (
            <>
              Search or jump to…
              <Kbd className="ml-auto">⌘K</Kbd>
            </>
          )}
        </button>
      </div>

      {/* Nav groups */}
      <nav className={`flex-1 overflow-y-auto py-3 space-y-4 ${collapsed ? 'px-2' : 'px-3'}`}>
        <div>
          {item({ to: '/', icon: Home, label: 'Home', tour: 'dashboard' })}
        </div>

        <div>
          <GroupLabel collapsed={collapsed}>Learn</GroupLabel>
          {item({ to: '/study', icon: GraduationCap, label: 'Study', tour: 'study' })}
          {item({ to: '/ask', icon: MessageSquare, label: 'Ask', tour: 'ask' })}
          {item({ to: '/knowledge', icon: Network, label: 'Knowledge', tour: 'knowledge' })}
        </div>

        <div>
          <GroupLabel collapsed={collapsed}>Library</GroupLabel>
          {!collapsed && (
            <button
              type="button"
              onClick={() => setCoursesExpanded(!coursesExpanded)}
              aria-expanded={coursesExpanded}
              aria-label={`Courses — ${coursesExpanded ? 'collapse' : 'expand'} list`}
              className="w-full flex items-center gap-2.5 px-2.5 py-1.5 rounded-lg text-[13px] text-text-muted hover:text-text hover:bg-surface-2/60 transition-colors cursor-pointer"
            >
              <Library size={15} strokeWidth={1.8} className="shrink-0 text-text-faint" aria-hidden />
              <span>Courses</span>
              <ChevronRight
                size={12}
                aria-hidden
                className={`ml-auto text-text-faint transition-transform ${coursesExpanded ? 'rotate-90' : ''}`}
              />
            </button>
          )}
          {!collapsed && coursesExpanded && (
            <div className="ml-1">
              {(courses ?? []).map((course) => (
                <NavItem
                  key={course.id}
                  to={`/courses/${course.code}`}
                  icon={Library}
                  label={course.code}
                  active={location.pathname.startsWith(`/courses/${course.code}`)}
                  collapsed={false}
                  indent
                />
              ))}
            </div>
          )}
          {item({ to: '/upload', icon: Upload, label: 'Upload', tour: 'upload' })}
          {item({ to: '/review', icon: Inbox, label: 'Review inbox', badge: pendingCount })}
        </div>

        <div>
          <GroupLabel collapsed={collapsed}>Insights</GroupLabel>
          {item({ to: '/analytics', icon: BarChart3, label: 'Analytics', tour: 'analytics' })}
          {item({ to: '/achievements', icon: Trophy, label: 'Achievements' })}
        </div>
      </nav>

      {/* Footer */}
      <div className={`border-t border-border py-2.5 space-y-0.5 ${collapsed ? 'px-2' : 'px-3'}`}>
        {item({ to: '/settings', icon: Settings, label: 'Settings', tour: 'settings' })}
        {user?.role === 'admin' && item({ to: '/admin', icon: ShieldCheck, label: 'Admin' })}
        <div className={`flex ${collapsed ? 'justify-center' : ''}`}>
          <ThemeToggle showLabel={!collapsed} />
        </div>

        {/* User card */}
        <div className={`flex items-center gap-2.5 pt-2 ${collapsed ? 'justify-center' : 'px-2.5'}`}>
          <Link to="/profile" aria-label="Profile" className="shrink-0">
            {user?.avatar_url ? (
              <img src={user.avatar_url} alt={user.username} className="w-6 h-6 rounded-full object-cover" />
            ) : (
              <span className="w-6 h-6 rounded-full bg-peri-soft text-peri-fg flex items-center justify-center text-[10px] font-bold">
                {user ? user.username.charAt(0).toUpperCase() : <UserIcon size={12} aria-hidden />}
              </span>
            )}
          </Link>
          {!collapsed && (
            <>
              <Link to="/profile" className="text-xs text-text-muted hover:text-text truncate transition-colors">
                {user?.username ?? 'guest'}
              </Link>
              {isDemo && <Badge variant="warning">Demo</Badge>}
              {isSelfHosted ? (
                <span className="ml-auto text-[10px] font-mono text-text-faint">self-hosted</span>
              ) : (
                <button
                  type="button"
                  onClick={() => logout()}
                  aria-label="Sign out"
                  className="ml-auto p-1 rounded-md text-text-faint hover:text-red-fg transition-colors cursor-pointer"
                >
                  <LogOut size={13} aria-hidden />
                </button>
              )}
            </>
          )}
        </div>
      </div>

      {/* Notification center (E2) */}
      <Sheet
        open={notificationsOpen}
        onOpenChange={setNotificationsOpen}
        side="right"
        title="Notifications"
        titleVisible={false}
      >
        <NotificationCenter onNavigate={() => setNotificationsOpen(false)} />
      </Sheet>
    </aside>
  )
}
