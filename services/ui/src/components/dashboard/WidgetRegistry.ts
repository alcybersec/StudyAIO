import type { ResponsiveLayouts } from 'react-grid-layout'

export interface WidgetDef {
  key: string
  label: string
  defaultVisible: boolean
  /** Minimum grid units — resizing and sanitization never go below these. */
  minW: number
  minH: number
}

/**
 * Bump when the widget set or default geometry changes in a way that makes
 * previously-persisted layouts invalid. `parseStored` discards any saved
 * layout whose version doesn't match, so stale/corrupt geometry (e.g. the
 * pre-rework 1×1 widgets) is replaced with fresh defaults on next load.
 */
export const LAYOUT_VERSION = 2

export const widgets: WidgetDef[] = [
  { key: 'streak', label: 'Streak', defaultVisible: true, minW: 4, minH: 3 },
  { key: 'exams', label: 'Exam Countdown', defaultVisible: true, minW: 4, minH: 3 },
  { key: 'gamification', label: 'Gamification', defaultVisible: true, minW: 4, minH: 3 },
  { key: 'study', label: 'Study Progress', defaultVisible: true, minW: 6, minH: 5 },
  { key: 'deadlines', label: 'Upcoming Deadlines', defaultVisible: true, minW: 4, minH: 3 },
  { key: 'activity', label: 'Activity Feed', defaultVisible: true, minW: 4, minH: 5 },
  { key: 'upload', label: 'Quick Upload', defaultVisible: true, minW: 3, minH: 4 },
  { key: 'courses', label: 'Your Courses', defaultVisible: true, minW: 6, minH: 4 },
]

export const widgetByKey: Record<string, WidgetDef> = Object.fromEntries(
  widgets.map((w) => [w.key, w]),
)

export const defaultLayouts: ResponsiveLayouts = {
  lg: [
    { i: 'streak', x: 0, y: 0, w: 6, h: 3, minW: 4, minH: 3 },
    { i: 'exams', x: 6, y: 0, w: 6, h: 3, minW: 4, minH: 3 },
    { i: 'gamification', x: 0, y: 3, w: 12, h: 3, minW: 4, minH: 3 },
    { i: 'study', x: 0, y: 6, w: 12, h: 6, minW: 6, minH: 5 },
    { i: 'deadlines', x: 0, y: 12, w: 6, h: 5, minW: 4, minH: 3 },
    { i: 'activity', x: 6, y: 12, w: 6, h: 5, minW: 4, minH: 5 },
    { i: 'upload', x: 0, y: 17, w: 6, h: 4, minW: 3, minH: 4 },
    { i: 'courses', x: 6, y: 17, w: 6, h: 4, minW: 6, minH: 4 },
  ],
  sm: [
    { i: 'streak', x: 0, y: 0, w: 12, h: 3, minW: 4, minH: 3 },
    { i: 'exams', x: 0, y: 3, w: 12, h: 3, minW: 4, minH: 3 },
    { i: 'gamification', x: 0, y: 6, w: 12, h: 3, minW: 4, minH: 3 },
    { i: 'study', x: 0, y: 9, w: 12, h: 6, minW: 6, minH: 5 },
    { i: 'deadlines', x: 0, y: 15, w: 12, h: 4, minW: 4, minH: 3 },
    { i: 'activity', x: 0, y: 19, w: 12, h: 5, minW: 4, minH: 5 },
    { i: 'upload', x: 0, y: 24, w: 12, h: 4, minW: 3, minH: 4 },
    { i: 'courses', x: 0, y: 28, w: 12, h: 4, minW: 6, minH: 4 },
  ],
}
