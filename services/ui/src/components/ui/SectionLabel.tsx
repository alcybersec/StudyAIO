interface SectionLabelProps {
  children: React.ReactNode
  className?: string
}

/** Quiet mono section label — the prototype's uppercase tracking style. */
export function SectionLabel({ children, className = '' }: SectionLabelProps) {
  return (
    <div
      className={`text-[10px] font-mono font-medium uppercase tracking-[0.12em] text-text-faint mb-2 ${className}`}
    >
      {children}
    </div>
  )
}
