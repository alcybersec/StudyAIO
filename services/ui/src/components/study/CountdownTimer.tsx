import { useEffect, useRef, useState } from 'react'

interface CountdownTimerProps {
  totalSeconds: number
  onTimeUp: () => void
  paused?: boolean
}

export function CountdownTimer({ totalSeconds, onTimeUp, paused = false }: CountdownTimerProps) {
  const [remaining, setRemaining] = useState(totalSeconds)
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    if (paused || remaining <= 0) {
      if (intervalRef.current) clearInterval(intervalRef.current)
      return
    }

    intervalRef.current = setInterval(() => {
      setRemaining((prev) => {
        if (prev <= 1) {
          onTimeUp()
          return 0
        }
        return prev - 1
      })
    }, 1000)

    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current)
    }
  }, [paused, remaining, onTimeUp])

  const minutes = Math.floor(remaining / 60)
  const seconds = remaining % 60
  const pct = (remaining / totalSeconds) * 100

  // Color thresholds
  let colorClass = 'text-green-600'
  let barColor = 'bg-green-500'
  if (pct < 20) {
    colorClass = 'text-red-600'
    barColor = 'bg-red-500'
  } else if (pct < 50) {
    colorClass = 'text-amber-600'
    barColor = 'bg-amber-500'
  }

  return (
    <div className="flex items-center gap-3">
      <div className={`text-2xl font-mono font-bold tabular-nums ${colorClass}`}>
        {String(minutes).padStart(2, '0')}:{String(seconds).padStart(2, '0')}
      </div>
      <div className="flex-1 h-2 bg-border rounded-full overflow-hidden">
        <div
          className={`h-full ${barColor} transition-all duration-1000 ease-linear rounded-full`}
          style={{ width: `${pct}%` }}
        />
      </div>
      {paused && (
        <span className="text-xs text-text-muted font-medium">PAUSED</span>
      )}
    </div>
  )
}
