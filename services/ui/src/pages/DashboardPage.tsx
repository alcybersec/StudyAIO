import { useCallback, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { ResponsiveGridLayout, useContainerWidth } from 'react-grid-layout'
import 'react-grid-layout/css/styles.css'
import 'react-resizable/css/styles.css'
import { Flame, Settings2 } from 'lucide-react'
import { useDashboard } from '../hooks/useApi'
import { useDashboardLayout } from '../hooks/useDashboardLayout'
import { Button } from '../components/ui'
import { ReviewAlert } from '../components/dashboard/ReviewAlert'
import { DashboardCustomizer } from '../components/dashboard/DashboardCustomizer'
import { MeasuredCell } from '../components/dashboard/MeasuredCell'
import { ROW_HEIGHT, GRID_MARGIN, rowsForHeight, alignRows } from '../components/dashboard/layoutUtils'
import type { ResponsiveLayouts } from 'react-grid-layout'
import { StreakWidget } from '../components/dashboard/widgets/StreakWidget'
import { ExamsWidget } from '../components/dashboard/widgets/ExamsWidget'
import { GamificationWidget } from '../components/dashboard/widgets/GamificationWidget'
import { StudyProgressWidget } from '../components/dashboard/widgets/StudyProgressWidget'
import { DeadlinesWidget } from '../components/dashboard/widgets/DeadlinesWidget'
import { ActivityWidget } from '../components/dashboard/widgets/ActivityWidget'
import { QuickUploadWidget } from '../components/dashboard/widgets/QuickUploadWidget'
import { CoursesWidget } from '../components/dashboard/widgets/CoursesWidget'
import { AchievementUnlock } from '../components/gamification/AchievementUnlock'
import { InstallPrompt } from '../components/pwa/InstallPrompt'

export function DashboardPage() {
  // Header metadata only — the widget grid never blocks on this query.
  // Each widget owns its slice of the same cache entry with isolated states.
  const { data } = useDashboard()
  const { layouts, hiddenWidgets, visibleWidgets, onLayoutChange, toggleWidget, resetLayout } = useDashboardLayout()
  const [customizerOpen, setCustomizerOpen] = useState(false)
  const { width, containerRef } = useContainerWidth()

  // Measured content height per widget. Cells are sized to fit so a widget
  // never clips or scrolls, whatever its data state. ~140px is a sane guess
  // before the first measurement lands.
  const [heights, setHeights] = useState<Record<string, number>>({})
  const onMeasure = useCallback((key: string, px: number) => {
    setHeights((prev) => (Math.abs((prev[key] ?? 0) - px) < 3 ? prev : { ...prev, [key]: px }))
  }, [])

  const today = useMemo(
    () => new Date().toLocaleDateString(undefined, { weekday: 'long', month: 'long', day: 'numeric' }),
    [],
  )

  // Static element map — widgets fetch their own data, so this never changes.
  const widgetContent = useMemo<Record<string, React.ReactNode>>(
    () => ({
      streak: <StreakWidget />,
      exams: <ExamsWidget />,
      gamification: <GamificationWidget />,
      study: <StudyProgressWidget />,
      deadlines: <DeadlinesWidget />,
      activity: <ActivityWidget />,
      upload: <QuickUploadWidget />,
      courses: <CoursesWidget />,
    }),
    [],
  )

  const activeWidgets = useMemo(
    () => visibleWidgets.filter((w) => widgetContent[w.key] !== undefined),
    [visibleWidgets, widgetContent],
  )

  // Filter to active widgets, drive each item's height from its measured
  // content (so nothing clips or scrolls), then snap every row to its tallest
  // widget so cards line up and rows share a baseline.
  const DEFAULT_H = rowsForHeight(140)
  const filteredLayouts = useMemo(() => {
    const activeKeys = new Set(activeWidgets.map((w) => w.key))
    const result: Record<string, unknown[]> = {}
    const rowsOf = (key: string) => (heights[key] ? rowsForHeight(heights[key]) : DEFAULT_H)
    for (const [bp, items] of Object.entries(layouts)) {
      if (!Array.isArray(items)) continue
      const filtered = (items as { i: string; x: number; y: number; w: number }[]).filter((item) =>
        activeKeys.has(item.i),
      )
      result[bp] = alignRows(filtered, rowsOf)
    }
    return result as ResponsiveLayouts
    // DEFAULT_H is derived from a constant; excluded intentionally.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [layouts, activeWidgets, heights])

  const courseCount = data?.courses.length
  const streakDays = data?.streak?.current_streak ?? 0

  return (
    <div ref={containerRef}>
      <div className="flex items-start justify-between mb-6 gap-4">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-text">Home</h1>
          <p className="text-xs text-text-muted mt-1">
            {today}
            {courseCount !== undefined && (
              <>
                {' · '}
                {courseCount} course{courseCount !== 1 ? 's' : ''}
              </>
            )}
            {streakDays > 0 && (
              <>
                {' · '}
                <span className="text-amber-fg font-semibold inline-flex items-center gap-1">
                  <Flame size={11} aria-hidden /> {streakDays}-day streak
                </span>
              </>
            )}
          </p>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <Button variant="ghost" size="sm" onClick={() => setCustomizerOpen(true)} aria-label="Customize dashboard">
            <Settings2 size={13} aria-hidden /> Customize
          </Button>
          <Link
            to="/study"
            className="inline-flex items-center gap-1.5 text-xs font-medium px-2.5 py-1.5 rounded-md bg-sage text-on-accent hover:bg-sage-hover transition-colors"
          >
            Start session
          </Link>
        </div>
      </div>

      <ReviewAlert />

      {/* On narrow viewports, stack widgets naturally for auto-sizing (no fixed grid heights).
          On wide viewports, use the draggable grid layout. */}
      {(width ?? 1200) < 1024 ? (
        <div className="flex flex-col gap-4">
          {activeWidgets.map((w) => (
            <div key={w.key}>{widgetContent[w.key]}</div>
          ))}
        </div>
      ) : (
        <ResponsiveGridLayout
          className="layout"
          width={width ?? 1200}
          layouts={filteredLayouts}
          breakpoints={{ lg: 1024, sm: 0 }}
          cols={{ lg: 12, sm: 12 }}
          rowHeight={ROW_HEIGHT}
          onLayoutChange={onLayoutChange}
          dragConfig={{
            enabled: true,
            handle: '.drag-handle',
          }}
          resizeConfig={{
            // Heights are content-driven; manual resize would fight the
            // measured layout, so widgets are drag-to-reorder only.
            enabled: false,
          }}
          containerPadding={[0, 0] as const}
          margin={[GRID_MARGIN, GRID_MARGIN] as const}
        >
          {activeWidgets.map((w) => (
            <div key={w.key} className="relative group rounded-xl">
              <div className="drag-handle absolute top-0 left-0 right-0 h-6 cursor-grab active:cursor-grabbing z-10 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                <div className="w-8 h-1 rounded-full bg-border" />
              </div>
              <MeasuredCell widgetKey={w.key} onMeasure={onMeasure}>
                {widgetContent[w.key]}
              </MeasuredCell>
            </div>
          ))}
        </ResponsiveGridLayout>
      )}

      <DashboardCustomizer
        open={customizerOpen}
        onOpenChange={setCustomizerOpen}
        hiddenWidgets={hiddenWidgets}
        onToggle={toggleWidget}
        onReset={resetLayout}
      />

      <AchievementUnlock />
      <InstallPrompt />
    </div>
  )
}
