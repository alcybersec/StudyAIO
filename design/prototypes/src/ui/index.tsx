import { type ReactNode, type ButtonHTMLAttributes, type InputHTMLAttributes } from 'react'
import { Loader2, RefreshCw, ChevronDown, Inbox } from 'lucide-react'

/* ---------------------------------------------------------------- Button */

type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger'
type ButtonSize = 'sm' | 'md' | 'lg'

const btnVariant: Record<ButtonVariant, string> = {
  primary: 'bg-sage text-on-accent hover:bg-sage-hover border border-transparent',
  secondary: 'bg-surface-1 text-text border border-border hover:bg-surface-2',
  ghost: 'bg-transparent text-text-muted hover:text-text hover:bg-surface-2 border border-transparent',
  danger: 'bg-red text-on-accent hover:opacity-90 border border-transparent',
}
const btnSize: Record<ButtonSize, string> = {
  sm: 'text-xs px-2.5 py-1.5 rounded-md gap-1.5',
  md: 'text-sm px-3.5 py-2 rounded-lg gap-2',
  lg: 'text-sm px-5 py-2.5 rounded-lg gap-2 font-semibold',
}

export function Button({
  variant = 'primary',
  size = 'md',
  loading,
  kbd,
  children,
  className = '',
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant
  size?: ButtonSize
  loading?: boolean
  kbd?: string
}) {
  return (
    <button
      className={`inline-flex items-center justify-center font-medium transition-colors disabled:opacity-45 disabled:cursor-not-allowed cursor-pointer ${btnVariant[variant]} ${btnSize[size]} ${className}`}
      disabled={loading || rest.disabled}
      {...rest}
    >
      {loading && <Loader2 size={14} className="animate-spin" aria-hidden />}
      {children}
      {kbd && <kbd className="ml-1 opacity-80">{kbd}</kbd>}
    </button>
  )
}

/* ----------------------------------------------------------------- Input */

export function Input({
  label,
  error,
  id,
  className = '',
  ...rest
}: InputHTMLAttributes<HTMLInputElement> & { label?: string; error?: string }) {
  const errId = error && id ? `${id}-error` : undefined
  return (
    <div className={className}>
      {label && (
        <label htmlFor={id} className="block text-xs font-medium text-text-muted mb-1.5">
          {label}
        </label>
      )}
      <input
        id={id}
        aria-invalid={!!error}
        aria-describedby={errId}
        className={`w-full bg-surface-1 border rounded-lg px-3 py-2 text-sm text-text placeholder:text-text-faint transition-colors ${
          error ? 'border-red' : 'border-border hover:border-border-strong focus:border-peri'
        }`}
        {...rest}
      />
      {error && (
        <p id={errId} role="alert" className="text-xs text-red-fg mt-1.5">
          {error}
        </p>
      )}
    </div>
  )
}

/* ------------------------------------------------------------------ Card */

export function Card({ children, className = '', dense }: { children: ReactNode; className?: string; dense?: boolean }) {
  return (
    <div className={`bg-surface-1 border border-border rounded-xl ${dense ? 'p-3' : 'p-4'} ${className}`}>
      {children}
    </div>
  )
}

/* ----------------------------------------------------------------- Badge */

type Tone = 'sage' | 'amber' | 'red' | 'peri' | 'muted'
const badgeTone: Record<Tone, string> = {
  sage: 'bg-sage-soft text-sage-fg',
  amber: 'bg-amber-soft text-amber-fg',
  red: 'bg-red-soft text-red-fg',
  peri: 'bg-peri-soft text-peri-fg',
  muted: 'bg-surface-2 text-text-muted',
}

export function Badge({ tone = 'muted', children, className = '' }: { tone?: Tone; children: ReactNode; className?: string }) {
  return (
    <span className={`inline-flex items-center gap-1 text-[11px] font-medium px-2 py-0.5 rounded-md ${badgeTone[tone]} ${className}`}>
      {children}
    </span>
  )
}

/* -------------------------------------------------------------- Skeleton */

export function Skeleton({ className = '' }: { className?: string }) {
  return <div className={`animate-pulse bg-surface-2 rounded-md ${className}`} aria-hidden />
}

export function SkeletonRows({ rows = 3 }: { rows?: number }) {
  return (
    <div className="space-y-2.5" role="status" aria-label="Loading">
      {Array.from({ length: rows }).map((_, i) => (
        <Skeleton key={i} className={`h-4 ${i % 3 === 0 ? 'w-3/4' : i % 3 === 1 ? 'w-full' : 'w-1/2'}`} />
      ))}
    </div>
  )
}

/* ------------------------------------------------------------ EmptyState */

export function EmptyState({
  icon,
  title,
  hint,
  action,
}: {
  icon?: ReactNode
  title: string
  hint?: string
  action?: ReactNode
}) {
  return (
    <div className="flex flex-col items-center justify-center text-center py-10 px-6">
      <div className="text-text-faint mb-3">{icon ?? <Inbox size={28} strokeWidth={1.5} />}</div>
      <p className="text-sm font-medium text-text">{title}</p>
      {hint && <p className="text-xs text-text-muted mt-1 max-w-xs">{hint}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  )
}

/* ------------------------------------------------------------ ErrorState */

export function ErrorState({
  title = "This couldn't load",
  detail,
  onRetry,
  compact,
}: {
  title?: string
  detail?: string
  onRetry?: () => void
  compact?: boolean
}) {
  return (
    <div
      role="alert"
      className={`border border-red/30 bg-red-soft rounded-xl ${compact ? 'p-3' : 'p-5'} flex flex-col items-start gap-2`}
    >
      <p className="text-sm font-medium text-text">{title}</p>
      <p className="text-xs text-text-muted">
        The rest of the app is fine — this section hit a problem. Retrying usually fixes it.
      </p>
      <div className="flex items-center gap-3 mt-1">
        <Button variant="secondary" size="sm" onClick={onRetry}>
          <RefreshCw size={12} /> Retry
        </Button>
        {detail && (
          <details className="text-xs text-text-faint">
            <summary className="cursor-pointer hover:text-text-muted">details</summary>
            <code className="font-mono text-[11px] block mt-1 max-w-md">{detail}</code>
          </details>
        )}
      </div>
    </div>
  )
}

/* --------------------------------------------------------------- Section */

export function SectionLabel({ children }: { children: ReactNode }) {
  return (
    <div className="text-[10px] font-mono font-medium uppercase tracking-[0.12em] text-text-faint mb-2">
      {children}
    </div>
  )
}

/* ------------------------------------------------------------ FakeSelect */

export function FakeSelect({ value, label, className = '' }: { value: string; label?: string; className?: string }) {
  return (
    <div className={className}>
      {label && <span className="block text-xs font-medium text-text-muted mb-1.5">{label}</span>}
      <button className="w-full flex items-center justify-between bg-surface-1 border border-border hover:border-border-strong rounded-lg px-3 py-2 text-sm text-text cursor-pointer">
        {value}
        <ChevronDown size={14} className="text-text-faint" />
      </button>
    </div>
  )
}
