import { useEffect, useRef, type ReactNode } from 'react'

/**
 * Reports its content's natural pixel height to `onMeasure` whenever it
 * changes. Lets the dashboard size each grid cell to fit its widget so
 * content is never clipped or scrolled, regardless of data state.
 */
export function MeasuredCell({
  widgetKey,
  onMeasure,
  children,
}: {
  widgetKey: string
  onMeasure: (key: string, height: number) => void
  children: ReactNode
}) {
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const el = ref.current
    if (!el) return
    const report = () => onMeasure(widgetKey, el.offsetHeight)
    report()
    const ro = new ResizeObserver(report)
    ro.observe(el)
    return () => ro.disconnect()
  }, [widgetKey, onMeasure])

  return <div ref={ref}>{children}</div>
}
