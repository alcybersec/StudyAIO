import { useMemo, type ReactNode } from 'react'
import { WidgetMeasureContext } from './measureContext'

/**
 * Wraps a dashboard widget so its WidgetShell can report its natural content
 * height (via context) and fill the grid cell. The dashboard uses the reported
 * heights to size and align cells.
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
  const value = useMemo(() => ({ widgetKey, onMeasure }), [widgetKey, onMeasure])
  return (
    <WidgetMeasureContext.Provider value={value}>
      <div className="h-full">{children}</div>
    </WidgetMeasureContext.Provider>
  )
}
