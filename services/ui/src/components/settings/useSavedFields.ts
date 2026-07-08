import { useCallback, useEffect, useRef, useState } from 'react'

/**
 * Tracks transient per-field "saved" feedback for autosaving settings forms.
 * A field is flagged for a short window after a successful save, then cleared.
 */
export function useSavedFields(clearAfterMs = 2500) {
  const [saved, setSaved] = useState<Record<string, boolean>>({})
  const timers = useRef<Record<string, ReturnType<typeof setTimeout>>>({})

  useEffect(() => {
    const pending = timers.current
    return () => {
      Object.values(pending).forEach(clearTimeout)
    }
  }, [])

  const markSaved = useCallback(
    (field: string) => {
      setSaved((prev) => ({ ...prev, [field]: true }))
      clearTimeout(timers.current[field])
      timers.current[field] = setTimeout(() => {
        setSaved((prev) => {
          const next = { ...prev }
          delete next[field]
          return next
        })
      }, clearAfterMs)
    },
    [clearAfterMs],
  )

  return { saved, markSaved }
}
