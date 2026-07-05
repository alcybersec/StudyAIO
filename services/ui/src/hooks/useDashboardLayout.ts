import { useCallback, useMemo, useRef, useState } from 'react'
import type { ResponsiveLayouts } from 'react-grid-layout'
import { useSettings, useUpdateSettings } from './useApi'
import { defaultLayouts, widgets } from '../components/dashboard/WidgetRegistry'
import { sanitizeLayouts, serializeLayout } from '../components/dashboard/layoutUtils'

function parseStored(raw: Record<string, unknown> | null | undefined): {
  layouts: ResponsiveLayouts
  hiddenWidgets: string[]
} {
  // sanitizeLayouts version-gates and clamps; it never throws on bad input.
  const layouts = sanitizeLayouts(raw)
  const hiddenWidgets = Array.isArray(raw?.hiddenWidgets) ? (raw!.hiddenWidgets as string[]) : []
  return { layouts, hiddenWidgets }
}

export function useDashboardLayout() {
  const { data: settings } = useSettings()
  const updateSettings = useUpdateSettings()
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Local overrides — set when user drags/toggles, cleared when server catches up
  const [localLayouts, setLocalLayouts] = useState<ResponsiveLayouts | null>(null)
  const [localHidden, setLocalHidden] = useState<string[] | null>(null)

  const serverState = useMemo(
    () => parseStored(settings?.dashboard_layout),
    [settings?.dashboard_layout],
  )

  const layouts = localLayouts ?? serverState.layouts
  const hiddenWidgets = localHidden ?? serverState.hiddenWidgets

  const persist = useCallback(
    (newLayouts: ResponsiveLayouts, newHidden: string[]) => {
      if (debounceRef.current) clearTimeout(debounceRef.current)
      debounceRef.current = setTimeout(() => {
        updateSettings.mutate(
          { dashboard_layout: serializeLayout(newLayouts, newHidden) },
          {
            onSuccess: () => {
              // Clear local overrides once server has persisted
              setLocalLayouts(null)
              setLocalHidden(null)
            },
          },
        )
      }, 500)
    },
    [updateSettings],
  )

  const onLayoutChange = useCallback(
    (_currentLayout: unknown, allLayouts: ResponsiveLayouts) => {
      setLocalLayouts(allLayouts)
      persist(allLayouts, hiddenWidgets)
    },
    [hiddenWidgets, persist],
  )

  const toggleWidget = useCallback(
    (key: string) => {
      const prev = hiddenWidgets
      const next = prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key]
      setLocalHidden(next)
      persist(layouts, next)
    },
    [layouts, hiddenWidgets, persist],
  )

  const resetLayout = useCallback(() => {
    setLocalLayouts(defaultLayouts)
    setLocalHidden([])
    persist(defaultLayouts, [])
  }, [persist])

  const visibleWidgets = widgets.filter((w) => !hiddenWidgets.includes(w.key))

  return {
    layouts,
    hiddenWidgets,
    visibleWidgets,
    onLayoutChange,
    toggleWidget,
    resetLayout,
  }
}
