import type { ResponsiveLayouts } from 'react-grid-layout'

export interface WidgetDef {
  key: string
  label: string
  defaultVisible: boolean
}

export const widgets: WidgetDef[] = [
  { key: 'streak', label: 'Streak', defaultVisible: true },
  { key: 'exams', label: 'Exam Countdown', defaultVisible: true },
  { key: 'gamification', label: 'Gamification', defaultVisible: true },
  { key: 'study', label: 'Study Progress', defaultVisible: true },
  { key: 'deadlines', label: 'Upcoming Deadlines', defaultVisible: true },
  { key: 'activity', label: 'Activity Feed', defaultVisible: true },
  { key: 'upload', label: 'Quick Upload', defaultVisible: true },
  { key: 'courses', label: 'Your Courses', defaultVisible: true },
]

export const defaultLayouts: ResponsiveLayouts = {
  lg: [
    { i: 'streak', x: 0, y: 0, w: 6, h: 3 },
    { i: 'exams', x: 6, y: 0, w: 6, h: 3 },
    { i: 'gamification', x: 0, y: 3, w: 12, h: 3 },
    { i: 'study', x: 0, y: 6, w: 12, h: 3 },
    { i: 'deadlines', x: 0, y: 9, w: 12, h: 4 },
    { i: 'activity', x: 0, y: 13, w: 8, h: 5 },
    { i: 'upload', x: 8, y: 13, w: 4, h: 5 },
    { i: 'courses', x: 0, y: 18, w: 12, h: 4 },
  ],
  sm: [
    { i: 'streak', x: 0, y: 0, w: 12, h: 3 },
    { i: 'exams', x: 0, y: 3, w: 12, h: 3 },
    { i: 'gamification', x: 0, y: 6, w: 12, h: 3 },
    { i: 'study', x: 0, y: 9, w: 12, h: 3 },
    { i: 'deadlines', x: 0, y: 12, w: 12, h: 4 },
    { i: 'activity', x: 0, y: 16, w: 12, h: 5 },
    { i: 'upload', x: 0, y: 21, w: 12, h: 5 },
    { i: 'courses', x: 0, y: 26, w: 12, h: 4 },
  ],
}
