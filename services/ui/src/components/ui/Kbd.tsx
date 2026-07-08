import type { ReactNode } from 'react'

interface KbdProps {
  children: ReactNode
  className?: string
}

/**
 * Keyboard hint chip. Visual styling comes from the base `kbd` element rules
 * in index.css (mono font, surface-2 chip, bottom border) — this component
 * exists so JSX call-sites stay semantic and composable.
 */
export function Kbd({ children, className = '' }: KbdProps) {
  return <kbd className={className}>{children}</kbd>
}
