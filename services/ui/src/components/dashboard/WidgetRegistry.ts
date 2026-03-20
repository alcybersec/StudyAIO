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
    { i: 'study', x: 0, y: 6, w: 12, h: 8 },
    { i: 'deadlines', x: 0, y: 14, w: 12, h: 4 },
    { i: 'activity', x: 0, y: 18, w: 8, h: 9 },
    { i: 'upload', x: 8, y: 18, w: 4, h: 9 },
    { i: 'courses', x: 0, y: 27, w: 12, h: 6 },
  ],
  sm: [
    { i: 'streak', x: 0, y: 0, w: 12, h: 2 },
    { i: 'exams', x: 0, y: 2, w: 12, h: 3 },
    { i: 'gamification', x: 0, y: 5, w: 12, h: 3 },
    { i: 'study', x: 0, y: 8, w: 12, h: 8 },
    { i: 'deadlines', x: 0, y: 16, w: 12, h: 3 },
    { i: 'activity', x: 0, y: 19, w: 12, h: 9 },
    { i: 'upload', x: 0, y: 28, w: 12, h: 7 },
    { i: 'courses', x: 0, y: 35, w: 12, h: 6 },
  ],
}
