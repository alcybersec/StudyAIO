/** Format a second count as m:ss (e.g. 272 → "4:32"), clamped at zero. */
export function formatCountdown(totalSeconds: number): string {
  const clamped = Math.max(Math.floor(totalSeconds), 0)
  const minutes = Math.floor(clamped / 60)
  const seconds = clamped % 60
  return `${minutes}:${String(seconds).padStart(2, '0')}`
}
