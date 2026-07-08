import {
  Home, GraduationCap, MessageSquare, Network, Library, Upload, InboxIcon,
  BarChart3, Trophy, Settings, Bell, ChevronDown, Search, Zap, FileCheck, CalendarClock,
} from 'lucide-react'
import { Badge, SectionLabel } from '../ui'
import { notifications } from '../lib/mock'

function NavItem({ icon: Icon, label, active, badge, indent }: any) {
  return (
    <button
      className={`w-full flex items-center gap-2.5 px-2.5 py-1.5 rounded-lg text-[13px] cursor-pointer transition-colors ${
        active ? 'bg-surface-2 text-text font-medium' : 'text-text-muted hover:text-text hover:bg-surface-2/60'
      } ${indent ? 'pl-8' : ''}`}
    >
      {Icon && <Icon size={15} strokeWidth={1.8} className={active ? 'text-sage-fg' : 'text-text-faint'} />}
      <span className="truncate">{label}</span>
      {badge != null && <Badge tone="amber" className="ml-auto">{badge}</Badge>}
    </button>
  )
}

function DesktopSidebar() {
  return (
    <div className="w-56 bg-surface-1 border border-border rounded-xl flex flex-col overflow-hidden" style={{ height: 560 }}>
      {/* header: logo + bell */}
      <div className="flex items-center justify-between px-3.5 py-3 border-b border-border">
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded-md bg-sage flex items-center justify-center text-on-accent text-xs font-bold">S</div>
          <span className="text-sm font-bold tracking-tight">StudyAIO</span>
        </div>
        <button className="relative p-1.5 rounded-lg hover:bg-surface-2 cursor-pointer" aria-label="Notifications — 2 unread">
          <Bell size={15} className="text-text-muted" />
          <span className="absolute top-1 right-1 w-1.5 h-1.5 rounded-full bg-amber" />
        </button>
      </div>

      {/* search affordance */}
      <div className="px-3 pt-3">
        <button className="w-full flex items-center gap-2 px-2.5 py-1.5 rounded-lg border border-border text-[12px] text-text-faint hover:border-border-strong cursor-pointer">
          <Search size={13} /> Search or jump to… <kbd className="ml-auto">⌘K</kbd>
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-3 py-3 space-y-4">
        <div>
          <NavItem icon={Home} label="Home" active />
        </div>
        <div>
          <div className="text-[9px] font-mono uppercase tracking-[0.14em] text-text-faint px-2.5 mb-1">Learn</div>
          <NavItem icon={GraduationCap} label="Study" />
          <NavItem icon={MessageSquare} label="Ask" />
          <NavItem icon={Network} label="Knowledge" />
        </div>
        <div>
          <div className="text-[9px] font-mono uppercase tracking-[0.14em] text-text-faint px-2.5 mb-1">Library</div>
          <NavItem icon={Library} label="Courses" />
          <div className="ml-1">
            <NavItem label="CSIT302" indent />
            <NavItem label="CSCI368" indent />
            <NavItem label="CSCI317" indent />
          </div>
          <NavItem icon={Upload} label="Upload" />
          <NavItem icon={InboxIcon} label="Review inbox" badge={3} />
        </div>
        <div>
          <div className="text-[9px] font-mono uppercase tracking-[0.14em] text-text-faint px-2.5 mb-1">Insights</div>
          <NavItem icon={BarChart3} label="Analytics" />
          <NavItem icon={Trophy} label="Achievements" />
        </div>
      </div>

      <div className="border-t border-border px-3 py-2.5">
        <NavItem icon={Settings} label="Settings" />
        <div className="flex items-center gap-2.5 px-2.5 pt-2.5">
          <div className="w-6 h-6 rounded-full bg-peri-soft text-peri-fg flex items-center justify-center text-[10px] font-bold">A</div>
          <span className="text-xs text-text-muted">alex</span>
          <span className="ml-auto text-[10px] font-mono text-text-faint">self-hosted</span>
        </div>
      </div>
    </div>
  )
}

function NotificationPanel() {
  const icons: Record<string, any> = { pipeline: FileCheck, review: InboxIcon, achievement: Zap, deadline: CalendarClock }
  return (
    <div className="w-80 bg-surface-1 border border-border-strong rounded-xl shadow-2xl shadow-black/20 overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3 border-b border-border">
        <span className="text-sm font-semibold">Notifications</span>
        <button className="text-[11px] text-text-faint hover:text-text-muted cursor-pointer">mark all read</button>
      </div>
      <ul className="divide-y divide-border max-h-80 overflow-y-auto">
        {notifications.map((n) => {
          const Icon = icons[n.kind]
          return (
            <li key={n.id} className={`flex gap-3 px-4 py-3 ${n.unread ? '' : 'opacity-55'}`}>
              <span className={`mt-0.5 ${n.unread ? 'text-sage-fg' : 'text-text-faint'}`}>
                <Icon size={14} />
              </span>
              <div className="min-w-0">
                <p className="text-[13px] leading-snug">{n.text}</p>
                <p className="text-[10px] font-mono text-text-faint mt-1">{n.when}</p>
              </div>
              {n.unread && <span className="ml-auto mt-1.5 w-1.5 h-1.5 rounded-full bg-amber shrink-0" />}
            </li>
          )
        })}
      </ul>
      <div className="px-4 py-2.5 border-t border-border text-[10px] font-mono text-text-faint">
        pipeline · review · achievements · deadlines — all in one place, no toast spam
      </div>
    </div>
  )
}

function MobileBar() {
  const items = [
    { icon: Home, label: 'Home', active: true },
    { icon: GraduationCap, label: 'Study' },
    { icon: MessageSquare, label: 'Ask' },
    { icon: Library, label: 'Library' },
    { icon: ChevronDown, label: 'More' },
  ]
  return (
    <div className="w-72 bg-surface-1 border border-border rounded-xl p-2 flex justify-between">
      {items.map((it) => (
        <button key={it.label} className="flex flex-col items-center gap-1 px-3 py-1.5 cursor-pointer min-w-11">
          <it.icon size={17} strokeWidth={1.8} className={it.active ? 'text-sage-fg' : 'text-text-faint'} />
          <span className={`text-[9px] ${it.active ? 'text-text font-medium' : 'text-text-faint'}`}>{it.label}</span>
        </button>
      ))}
    </div>
  )
}

export function ShellNav() {
  return (
    <div className="px-8 py-8 max-w-5xl mx-auto">
      <div className="flex flex-wrap gap-10 items-start">
        <div>
          <SectionLabel>Desktop sidebar — Home / Learn / Library / Insights</SectionLabel>
          <DesktopSidebar />
        </div>
        <div className="space-y-8">
          <div>
            <SectionLabel>Notification center (bell in sidebar header)</SectionLabel>
            <NotificationPanel />
          </div>
          <div>
            <SectionLabel>Mobile bottom nav — mirrors the same groups</SectionLabel>
            <MobileBar />
            <p className="text-[11px] text-text-muted mt-3 max-w-xs leading-relaxed">
              "Library" opens a sheet with the course list — courses are finally browsable on mobile. "More" holds
              Review, Analytics, Achievements, Settings.
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
