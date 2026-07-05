import { describe, expect, it } from 'vitest'
import { sanitizeLayouts, serializeLayout, rowsForHeight, ROW_HEIGHT, GRID_MARGIN } from './layoutUtils'
import { defaultLayouts, widgetByKey, widgets, LAYOUT_VERSION } from './WidgetRegistry'

describe('rowsForHeight', () => {
  it('returns at least one row for tiny content', () => {
    expect(rowsForHeight(0)).toBe(1)
    expect(rowsForHeight(5)).toBe(1)
  })

  it('grows monotonically with content height', () => {
    expect(rowsForHeight(400)).toBeGreaterThan(rowsForHeight(140))
  })

  it('picks a row count whose pixel height covers the content (never clips)', () => {
    for (const px of [80, 140, 260, 512]) {
      const rows = rowsForHeight(px)
      const cellPx = rows * ROW_HEIGHT + (rows - 1) * GRID_MARGIN
      expect(cellPx).toBeGreaterThanOrEqual(px)
    }
  })
})

describe('sanitizeLayouts', () => {
  it('returns defaults when nothing is stored', () => {
    expect(sanitizeLayouts(null)).toEqual(defaultLayouts)
    expect(sanitizeLayouts(undefined)).toEqual(defaultLayouts)
    expect(sanitizeLayouts({})).toEqual(defaultLayouts)
  })

  it('discards a layout saved under an older version (the pre-rework corruption)', () => {
    // Reproduces the real bug: exams/study/deadlines persisted as 1×1 slivers.
    const corrupt = {
      // no version field → pre-rework
      layouts: {
        lg: [
          { i: 'streak', x: 0, y: 0, w: 6, h: 3 },
          { i: 'exams', x: 0, y: 3, w: 1, h: 1 },
          { i: 'study', x: 0, y: 12, w: 1, h: 1 },
          { i: 'deadlines', x: 0, y: 13, w: 1, h: 1 },
        ],
      },
      hiddenWidgets: [],
    }
    expect(sanitizeLayouts(corrupt)).toEqual(defaultLayouts)
  })

  it('keeps a current-version arrangement but clamps sub-minimum items', () => {
    const stored = {
      version: LAYOUT_VERSION,
      layouts: {
        lg: [
          { i: 'streak', x: 0, y: 0, w: 8, h: 5 }, // user-resized, valid → preserved
          { i: 'exams', x: 8, y: 0, w: 1, h: 1 }, // degenerate → clamped up
        ],
      },
      hiddenWidgets: [],
    }
    const result = sanitizeLayouts(stored)
    const lg = result.lg as unknown as { i: string; w: number; h: number }[]
    const streak = lg.find((i) => i.i === 'streak')!
    const exams = lg.find((i) => i.i === 'exams')!
    expect(streak.w).toBe(8)
    expect(streak.h).toBe(5)
    expect(exams.w).toBeGreaterThanOrEqual(widgetByKey.exams.minW)
    expect(exams.h).toBeGreaterThanOrEqual(widgetByKey.exams.minH)
  })

  it('includes every known widget even if the saved layout is missing some', () => {
    const stored = {
      version: LAYOUT_VERSION,
      layouts: { lg: [{ i: 'streak', x: 0, y: 0, w: 6, h: 3 }] },
      hiddenWidgets: [],
    }
    const lg = sanitizeLayouts(stored).lg as unknown as { i: string }[]
    expect(new Set(lg.map((i) => i.i))).toEqual(new Set(widgets.map((w) => w.key)))
  })

  it('drops items for unknown widget keys', () => {
    const stored = {
      version: LAYOUT_VERSION,
      layouts: { lg: [{ i: 'ghost_widget', x: 0, y: 0, w: 6, h: 3 }] },
      hiddenWidgets: [],
    }
    const lg = sanitizeLayouts(stored).lg as unknown as { i: string }[]
    expect(lg.some((i) => i.i === 'ghost_widget')).toBe(false)
  })

  it('never lets an item exceed the 12-column grid', () => {
    const stored = {
      version: LAYOUT_VERSION,
      layouts: { lg: [{ i: 'streak', x: 10, y: 0, w: 40, h: 3 }] },
      hiddenWidgets: [],
    }
    const streak = (sanitizeLayouts(stored).lg as unknown as { i: string; x: number; w: number }[]).find(
      (i) => i.i === 'streak',
    )!
    expect(streak.w).toBeLessThanOrEqual(12)
    expect(streak.x + streak.w).toBeLessThanOrEqual(12)
  })
})

describe('serializeLayout', () => {
  it('stamps the current version so future loads can validate it', () => {
    const out = serializeLayout(defaultLayouts, ['streak'])
    expect(out.version).toBe(LAYOUT_VERSION)
    expect(out.hiddenWidgets).toEqual(['streak'])
    // round-trips cleanly through the sanitizer
    expect(sanitizeLayouts(out)).toEqual(defaultLayouts)
  })
})
