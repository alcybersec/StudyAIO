import type { ReactNode } from 'react'

/** Mono uppercase micro-header used above widget and card sections. */
export function SectionLabel({ children, className = '' }: { children: ReactNode; className?: string }) {
  return (
    <div className={`text-[10px] font-mono font-medium uppercase tracking-[0.12em] text-text-faint mb-2 ${className}`}>
      {children}
    </div>
  )
}
