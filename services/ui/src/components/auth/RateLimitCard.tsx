import { useEffect, useRef, useState } from 'react'
import { Clock } from 'lucide-react'
import { formatCountdown } from './formatCountdown'

interface RateLimitCardProps {
  /** Initial cooldown in seconds. Re-key the component to restart it. */
  seconds: number
  /** Called once when the countdown reaches zero. */
  onExpire?: () => void
}

/**
 * 429 cooldown card per the Auth prototype: amber, distinct from a wrong
 * password, with a live mm:ss countdown so the user knows exactly how long
 * to wait instead of hammering the button.
 */
export function RateLimitCard({ seconds, onExpire }: RateLimitCardProps) {
  const [remaining, setRemaining] = useState(() => Math.max(Math.floor(seconds), 0))
  const onExpireRef = useRef(onExpire)

  useEffect(() => {
    onExpireRef.current = onExpire
  }, [onExpire])

  useEffect(() => {
    const id = setInterval(() => {
      setRemaining((current) => {
        const next = current - 1
        if (next <= 0) {
          clearInterval(id)
          if (current > 0) onExpireRef.current?.()
          return 0
        }
        return next
      })
    }, 1000)
    return () => clearInterval(id)
  }, [])

  return (
    <div
      role="status"
      className="rounded-xl border border-amber/25 bg-amber-soft px-4 py-3 flex items-center gap-2.5 text-xs text-amber-fg font-medium"
    >
      <Clock size={14} aria-hidden />
      <span>Too many attempts — try again in</span>
      <span className="ml-auto font-mono text-[13px] font-semibold tabular-nums">
        {formatCountdown(remaining)}
      </span>
    </div>
  )
}
