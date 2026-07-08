import type { CSSProperties } from 'react'
import { Toaster as SonnerToaster } from 'sonner'

// Sonner's built-in rich colors fail WCAG AA contrast (e.g. success green
// #008a2e on #ecfdf3 is 4.25:1). Override the typed-toast palettes with
// theme tokens: opaque surface background + AA-checked -fg text tones.
const tokenPalette = {
  '--success-bg': 'var(--t-surface-1)',
  '--success-text': 'var(--t-sage-fg)',
  '--success-border': 'var(--t-sage)',
  '--error-bg': 'var(--t-surface-1)',
  '--error-text': 'var(--t-red-fg)',
  '--error-border': 'var(--t-red)',
  '--warning-bg': 'var(--t-surface-1)',
  '--warning-text': 'var(--t-amber-fg)',
  '--warning-border': 'var(--t-amber)',
  '--info-bg': 'var(--t-surface-1)',
  '--info-text': 'var(--t-peri-fg)',
  '--info-border': 'var(--t-peri)',
} as CSSProperties

export function Toaster() {
  return (
    <SonnerToaster
      position="bottom-right"
      toastOptions={{
        className: 'bg-surface-1 text-text border-border',
        duration: 4000,
      }}
      richColors
      closeButton
      style={tokenPalette}
    />
  )
}
