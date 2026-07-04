import { type ReactNode } from 'react'
import { WifiOff, RefreshCw } from 'lucide-react'
import { useSim } from '../lib/sim'

/** Page frame used by screen prototypes: header + optional offline banner. */
export function PageShell({
  title,
  subtitle,
  actions,
  children,
  wide,
}: {
  title: ReactNode
  subtitle?: ReactNode
  actions?: ReactNode
  children: ReactNode
  wide?: boolean
}) {
  const { sim } = useSim()
  return (
    <div className={`mx-auto px-6 py-6 ${wide ? 'max-w-6xl' : 'max-w-5xl'}`}>
      {sim === 'offline' && <OfflineBanner />}
      <div className="flex items-start justify-between mb-6 gap-4">
        <div>
          <h1 className="text-xl font-bold tracking-tight">{title}</h1>
          {subtitle && <p className="text-xs text-text-muted mt-1">{subtitle}</p>}
        </div>
        {actions && <div className="flex items-center gap-2 shrink-0">{actions}</div>}
      </div>
      {children}
    </div>
  )
}

export function OfflineBanner() {
  return (
    <div
      role="status"
      aria-live="polite"
      className="flex items-center gap-2.5 bg-amber-soft border border-amber/25 text-amber-fg rounded-lg px-3.5 py-2.5 mb-5 text-xs font-medium"
    >
      <WifiOff size={14} />
      You're offline — showing cached data. Study progress is being saved locally.
      <span className="ml-auto flex items-center gap-1.5 font-mono text-[11px]">
        <RefreshCw size={11} className="animate-spin" style={{ animationDuration: '3s' }} />
        2 queued
      </span>
    </div>
  )
}

/** Small persistent chip shown while study writes are queued (offline OR server errors). */
export function SyncChip({ count = 2 }: { count?: number }) {
  return (
    <span
      role="status"
      className="inline-flex items-center gap-1.5 text-[11px] font-medium bg-peri-soft text-peri-fg rounded-full px-2.5 py-1"
    >
      <RefreshCw size={10} className="animate-spin" style={{ animationDuration: '2s' }} />
      {count} unsaved · syncing
    </span>
  )
}
