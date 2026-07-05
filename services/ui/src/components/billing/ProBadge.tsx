interface ProBadgeProps {
  className?: string
}

export function ProBadge({ className = '' }: ProBadgeProps) {
  return (
    <span
      className={`inline-flex items-center px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wider rounded bg-amber-soft text-amber-fg border border-amber/30 ${className}`}
    >
      Pro
    </span>
  )
}
