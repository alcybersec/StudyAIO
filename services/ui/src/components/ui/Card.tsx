interface CardProps {
  children: React.ReactNode
  className?: string
  padding?: boolean
}

export function Card({ children, className = '', padding = true }: CardProps) {
  return (
    <div className={`bg-surface-1 rounded-xl border border-border ${padding ? 'p-6' : ''} ${className}`}>
      {children}
    </div>
  )
}
