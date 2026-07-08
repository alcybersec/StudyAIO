import { createContext, useContext } from 'react'

interface MeasureCtx {
  widgetKey: string
  onMeasure: (key: string, height: number) => void
}

/**
 * Lets WidgetShell report its natural content height (and know which widget it
 * is) without every widget component threading measurement props. DashboardPage
 * provides one per cell; outside the dashboard the context is absent and
 * measurement is a no-op.
 */
export const WidgetMeasureContext = createContext<MeasureCtx | null>(null)

export const useWidgetMeasure = () => useContext(WidgetMeasureContext)
