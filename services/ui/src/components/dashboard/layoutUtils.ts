import type { ResponsiveLayouts } from 'react-grid-layout'
import { defaultLayouts, widgetByKey, widgets, LAYOUT_VERSION } from './WidgetRegistry'

interface LayoutItem {
  i: string
  x: number
  y: number
  w: number
  h: number
  minW?: number
  minH?: number
}

interface StoredLayout {
  version?: number
  layouts?: ResponsiveLayouts
  hiddenWidgets?: string[]
}

const COLS = 12

/**
 * Grid geometry. A small row height gives fine-grained control so a cell can
 * be sized to closely match its widget's measured content height.
 */
export const ROW_HEIGHT = 8
export const GRID_MARGIN = 16

/** Grid rows needed to fit `px` pixels of content (RGL height math). */
export function rowsForHeight(px: number): number {
  return Math.max(1, Math.ceil((px + GRID_MARGIN) / (ROW_HEIGHT + GRID_MARGIN)))
}

/**
 * Clamp a single item against its widget's registry minimums and the column
 * count. A saved item narrower/shorter than the widget's minimum (the classic
 * corrupt `w:1 h:1`) is snapped back up so its content can never be clipped.
 */
function clampItem(item: LayoutItem): LayoutItem {
  const def = widgetByKey[item.i]
  const minW = def?.minW ?? 3
  const minH = def?.minH ?? 3
  const w = Math.min(COLS, Math.max(minW, Math.round(item.w) || minW))
  const h = Math.max(minH, Math.round(item.h) || minH)
  const x = Math.min(COLS - w, Math.max(0, Math.round(item.x) || 0))
  const y = Math.max(0, Math.round(item.y) || 0)
  return { i: item.i, x, y, w, h, minW, minH }
}

/**
 * Produce a safe set of layouts from whatever was persisted.
 *
 * - Wrong/absent version → fall back to defaults entirely (discards pre-rework
 *   and otherwise-incompatible geometry).
 * - Right version → keep the user's arrangement but clamp every item to its
 *   widget minimums, drop items for unknown widget keys, and add any widget
 *   missing from the saved layout using its default position.
 */
export function sanitizeLayouts(raw: unknown): ResponsiveLayouts {
  const stored = (raw ?? {}) as StoredLayout
  if (stored.version !== LAYOUT_VERSION || !stored.layouts) {
    return defaultLayouts
  }

  const result: ResponsiveLayouts = {}
  for (const bp of Object.keys(defaultLayouts) as (keyof ResponsiveLayouts)[]) {
    const savedItems = (stored.layouts[bp] as LayoutItem[] | undefined) ?? []
    const bySavedKey = new Map(
      savedItems.filter((it) => widgetByKey[it.i]).map((it) => [it.i, it]),
    )
    // One entry per known widget, in registry order; saved geometry when present.
    result[bp] = widgets.map((w, idx) => {
      const saved = bySavedKey.get(w.key)
      if (saved) return clampItem(saved)
      const fallback = (defaultLayouts[bp] as LayoutItem[]).find((d) => d.i === w.key)
      return clampItem(fallback ?? { i: w.key, x: 0, y: idx * w.minH, w: w.minW, h: w.minH })
    })
  }
  return result
}

export function serializeLayout(
  layouts: ResponsiveLayouts,
  hiddenWidgets: string[],
): Record<string, unknown> {
  return { version: LAYOUT_VERSION, layouts, hiddenWidgets }
}
