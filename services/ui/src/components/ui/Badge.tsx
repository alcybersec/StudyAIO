interface BadgeProps {
  children: React.ReactNode
  variant?: 'default' | 'success' | 'warning' | 'danger' | 'info' | 'count'
  size?: 'sm' | 'md'
}

const variantClasses: Record<string, string> = {
  default: 'bg-surface-2 text-text-muted',
  success: 'bg-sage-soft text-sage-fg',
  warning: 'bg-amber-soft text-amber-fg',
  danger: 'bg-red-soft text-red-fg',
  info: 'bg-peri-soft text-peri-fg',
  count: 'bg-peri text-on-accent',
}

export function Badge({ children, variant = 'default', size = 'sm' }: BadgeProps) {
  const sizeClass = size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-2.5 py-1 text-sm'
  return (
    <span className={`inline-flex items-center font-medium rounded-full ${sizeClass} ${variantClasses[variant]}`}>
      {children}
    </span>
  )
}
