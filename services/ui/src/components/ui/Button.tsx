import type { ButtonHTMLAttributes } from 'react'
import { Loader2 } from 'lucide-react'
import { Kbd } from './Kbd'

export type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger'
export type ButtonSize = 'sm' | 'md' | 'lg'

const variantClasses: Record<ButtonVariant, string> = {
  primary: 'bg-sage text-on-accent hover:bg-sage-hover border border-transparent',
  secondary: 'bg-surface-1 text-text border border-border hover:bg-surface-2',
  ghost: 'bg-transparent text-text-muted hover:text-text hover:bg-surface-2 border border-transparent',
  danger: 'bg-red text-on-accent hover:opacity-90 border border-transparent',
}

const sizeClasses: Record<ButtonSize, string> = {
  sm: 'text-xs px-2.5 py-1.5 rounded-md gap-1.5',
  md: 'text-sm px-3.5 py-2 rounded-lg gap-2',
  lg: 'text-sm px-5 py-2.5 rounded-lg gap-2 font-semibold',
}

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant
  size?: ButtonSize
  loading?: boolean
  kbd?: string
}

export function Button({
  variant = 'primary',
  size = 'md',
  loading,
  kbd,
  children,
  className = '',
  disabled,
  ...rest
}: ButtonProps) {
  return (
    <button
      className={`inline-flex items-center justify-center font-medium transition-colors cursor-pointer disabled:opacity-45 disabled:cursor-not-allowed focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-peri ${variantClasses[variant]} ${sizeClasses[size]} ${className}`}
      disabled={loading || disabled}
      {...rest}
    >
      {loading && <Loader2 size={14} className="animate-spin" aria-hidden />}
      {children}
      {kbd && <Kbd className="ml-1 opacity-80">{kbd}</Kbd>}
    </button>
  )
}
