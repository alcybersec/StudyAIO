import type { ReactNode } from 'react'

interface TableProps {
  children: ReactNode
  className?: string
}

/** Dense data table per the course-page prototype: 13px rows, mono-uppercase head. */
export function Table({ children, className = '' }: TableProps) {
  return (
    <div className="overflow-x-auto">
      <table className={`w-full text-[13px] ${className}`}>{children}</table>
    </div>
  )
}

export function THead({ children }: { children: ReactNode }) {
  return (
    <thead>
      <tr className="text-left text-[10px] font-mono font-medium uppercase tracking-[0.1em] text-text-faint">
        {children}
      </tr>
    </thead>
  )
}

export function TBody({ children }: { children: ReactNode }) {
  return <tbody className="divide-y divide-border">{children}</tbody>
}

interface TRowProps {
  children: ReactNode
  onClick?: () => void
  className?: string
}

export function TRow({ children, onClick, className = '' }: TRowProps) {
  return (
    <tr
      onClick={onClick}
      onKeyDown={
        onClick
          ? (e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault()
                onClick()
              }
            }
          : undefined
      }
      tabIndex={onClick ? 0 : undefined}
      role={onClick ? 'button' : undefined}
      className={`${onClick ? 'hover:bg-surface-2/60 cursor-pointer focus-visible:outline focus-visible:outline-2 focus-visible:outline-peri' : ''} ${className}`}
    >
      {children}
    </tr>
  )
}

interface TCellProps {
  children?: ReactNode
  header?: boolean
  align?: 'left' | 'right'
  /** Absorb the table's remaining width (use on the primary column so the
   *  compact columns pack together instead of spreading unevenly). */
  grow?: boolean
  className?: string
}

export function TCell({ children, header, align = 'left', grow, className = '' }: TCellProps) {
  const alignClass = align === 'right' ? 'text-right' : ''
  // Horizontal padding gives columns breathing room; first/last stay flush to
  // the table edges so content lines up with the surrounding card. A `grow`
  // cell takes the slack so remaining columns size to their content.
  const pad = 'px-3 first:pl-0 last:pr-0'
  const growClass = grow ? 'w-full' : 'whitespace-nowrap'
  if (header) {
    return <th className={`font-medium py-1.5 ${pad} ${growClass} ${alignClass} ${className}`}>{children}</th>
  }
  return <td className={`py-2 ${pad} ${growClass} ${alignClass} ${className}`}>{children}</td>
}
