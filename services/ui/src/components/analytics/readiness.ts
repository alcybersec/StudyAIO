/** Mini accuracy bar tone: red below 60, amber below 70, sage otherwise. */
export function accuracyToneVar(pct: number): string {
  return pct < 60 ? 'var(--t-red)' : pct < 70 ? 'var(--t-amber)' : 'var(--t-sage)'
}

/** Weak = below the 70% quiz-accuracy threshold, or never studied at all. */
export function isWeakTopic(accuracy: number | null): boolean {
  return accuracy === null || accuracy < 70
}

/** Accuracy figure text tone matching the bar thresholds. */
export function accuracyTextVar(accuracy: number | null): string {
  if (accuracy === null) return 'var(--t-text-faint)'
  if (accuracy < 60) return 'var(--t-red-fg)'
  if (accuracy < 70) return 'var(--t-amber-fg)'
  return 'var(--t-text-muted)'
}
