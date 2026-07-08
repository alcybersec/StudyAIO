import { useState, type ComponentType } from 'react'
import { Link, useLocation } from 'react-router-dom'
import {
  BarChart3,
  Bell,
  GraduationCap,
  Home,
  Inbox,
  Library,
  MessageSquare,
  MoreHorizontal,
  Network,
  Settings,
  ShieldCheck,
  Trophy,
  Upload,
  User as UserIcon,
} from 'lucide-react'
import { useDashboard, useCourses } from '../../hooks/useApi'
import { useAuth } from '../../hooks/useAuth'
import { useUnreadCount } from '../../hooks/useNotificationInbox'
import { NotificationCenter } from '../notifications/NotificationCenter'
import { Badge } from '../ui/Badge'
import { Sheet } from '../ui/Sheet'

type IconType = ComponentType<{ size?: number | string; strokeWidth?: number | string; className?: string }>

interface SheetLinkProps {
  to: string
  icon: IconType
  label: string
  active: boolean
  badge?: number
  onNavigate: () => void
}

function SheetLink({ to, icon: Icon, label, active, badge, onNavigate }: SheetLinkProps) {
  return (
    <Link
      to={to}
      onClick={onNavigate}
      aria-current={active ? 'page' : undefined}
      className={`flex items-center gap-3 px-3 py-3 rounded-lg text-sm font-medium transition-colors min-h-[44px] ${
        active ? 'bg-surface-2 text-text' : 'text-text-muted hover:text-text hover:bg-surface-2/60'
      }`}
    >
      <Icon size={17} strokeWidth={1.8} className={active ? 'text-sage-fg' : 'text-text-faint'} aria-hidden />
      <span>{label}</span>
      {badge != null && badge > 0 && (
        <span className="ml-auto">
          <Badge variant="warning">{badge > 9 ? '9+' : badge}</Badge>
        </span>
      )}
    </Link>
  )
}

export function MobileNav() {
  const location = useLocation()
  const { data: dashboard } = useDashboard()
  const { data: courses } = useCourses()
  const { user } = useAuth()
  const [libraryOpen, setLibraryOpen] = useState(false)
  const [moreOpen, setMoreOpen] = useState(false)
  const [notificationsOpen, setNotificationsOpen] = useState(false)
  const pendingCount = dashboard?.pending_review_count ?? 0
  const { data: unreadCount = 0 } = useUnreadCount()

  const isActive = (path: string) =>
    path === '/' ? location.pathname === '/' : location.pathname.startsWith(path)

  const tabs: { to: string; icon: IconType; label: string }[] = [
    { to: '/', icon: Home, label: 'Home' },
    { to: '/study', icon: GraduationCap, label: 'Study' },
    { to: '/ask', icon: MessageSquare, label: 'Ask' },
  ]

  const libraryActive =
    location.pathname.startsWith('/courses') ||
    location.pathname.startsWith('/upload')
  const morePaths = ['/review', '/analytics', '/achievements', '/settings', '/profile', '/admin', '/knowledge']
  const moreActive = morePaths.some(isActive)

  const tabClass = (active: boolean) =>
    `relative flex flex-col items-center justify-center gap-0.5 w-full h-full text-[10px] transition-colors min-h-[44px] cursor-pointer ${
      active ? 'text-text font-medium' : 'text-text-muted'
    }`

  const closeSheets = () => {
    setLibraryOpen(false)
    setMoreOpen(false)
  }

  return (
    <>
      <nav className="lg:hidden fixed bottom-0 inset-x-0 bg-surface-1 border-t border-border z-50 safe-area-pb">
        <div className="flex items-center justify-around h-14">
          {tabs.map((tab) => (
            <Link
              key={tab.to}
              to={tab.to}
              aria-label={tab.label}
              aria-current={isActive(tab.to) ? 'page' : undefined}
              className={tabClass(isActive(tab.to))}
            >
              <tab.icon size={17} strokeWidth={1.8} className={isActive(tab.to) ? 'text-sage-fg' : 'text-text-faint'} aria-hidden />
              <span>{tab.label}</span>
            </Link>
          ))}

          <button
            type="button"
            onClick={() => setLibraryOpen(true)}
            aria-label="Library"
            className={tabClass(libraryActive)}
          >
            <Library size={17} strokeWidth={1.8} className={libraryActive ? 'text-sage-fg' : 'text-text-faint'} aria-hidden />
            <span>Library</span>
          </button>

          <button
            type="button"
            onClick={() => setMoreOpen(true)}
            aria-label="More"
            className={tabClass(moreActive)}
          >
            <MoreHorizontal size={17} strokeWidth={1.8} className={moreActive ? 'text-sage-fg' : 'text-text-faint'} aria-hidden />
            <span>More</span>
            {pendingCount > 0 && (
              <span className="absolute top-1 right-1/4 w-1.5 h-1.5 rounded-full bg-amber" aria-hidden />
            )}
          </button>
        </div>
      </nav>

      {/* Library sheet: browsable course list + Upload */}
      <Sheet open={libraryOpen} onOpenChange={setLibraryOpen} side="bottom" title="Library">
        <div className="space-y-1 pb-4">
          {(courses ?? []).map((course) => (
            <SheetLink
              key={course.id}
              to={`/courses/${course.code}`}
              icon={Library}
              label={course.code}
              active={location.pathname.startsWith(`/courses/${course.code}`)}
              onNavigate={closeSheets}
            />
          ))}
          {(courses ?? []).length === 0 && (
            <p className="px-3 py-2 text-sm text-text-muted">No courses yet — upload a lecture to create one.</p>
          )}
          <SheetLink to="/upload" icon={Upload} label="Upload" active={isActive('/upload')} onNavigate={closeSheets} />
        </div>
      </Sheet>

      {/* More sheet: secondary destinations */}
      <Sheet open={moreOpen} onOpenChange={setMoreOpen} side="bottom" title="More">
        <div className="space-y-1 pb-4">
          <button
            type="button"
            onClick={() => {
              setMoreOpen(false)
              setNotificationsOpen(true)
            }}
            className="w-full flex items-center gap-3 px-3 py-3 rounded-lg text-sm font-medium transition-colors min-h-[44px] text-text-muted hover:text-text hover:bg-surface-2/60 cursor-pointer"
          >
            <Bell size={17} strokeWidth={1.8} className="text-text-faint" aria-hidden />
            <span>Notifications</span>
            {unreadCount > 0 && (
              <span className="ml-auto">
                <Badge variant="warning">{unreadCount > 9 ? '9+' : unreadCount}</Badge>
              </span>
            )}
          </button>
          <SheetLink
            to="/review"
            icon={Inbox}
            label="Review inbox"
            active={isActive('/review')}
            badge={pendingCount}
            onNavigate={closeSheets}
          />
          <SheetLink to="/knowledge" icon={Network} label="Knowledge" active={isActive('/knowledge')} onNavigate={closeSheets} />
          <SheetLink to="/analytics" icon={BarChart3} label="Analytics" active={isActive('/analytics')} onNavigate={closeSheets} />
          <SheetLink to="/achievements" icon={Trophy} label="Achievements" active={isActive('/achievements')} onNavigate={closeSheets} />
          <SheetLink to="/settings" icon={Settings} label="Settings" active={isActive('/settings')} onNavigate={closeSheets} />
          <SheetLink to="/profile" icon={UserIcon} label="Profile" active={isActive('/profile')} onNavigate={closeSheets} />
          {user?.role === 'admin' && (
            <SheetLink to="/admin" icon={ShieldCheck} label="Admin" active={isActive('/admin')} onNavigate={closeSheets} />
          )}
        </div>
      </Sheet>

      {/* Notification center (E2) */}
      <Sheet
        open={notificationsOpen}
        onOpenChange={setNotificationsOpen}
        side="bottom"
        title="Notifications"
        titleVisible={false}
      >
        <NotificationCenter onNavigate={() => setNotificationsOpen(false)} />
      </Sheet>
    </>
  )
}
