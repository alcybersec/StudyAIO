import { useMemo, useState } from 'react'
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

  // Filter layouts to only include active widgets and re-compact vertically
  const filteredLayouts = useMemo(() => {
    const activeKeys = new Set(activeWidgets.map((w) => w.key))
    const result: Record<string, unknown[]> = {}
    for (const [bp, items] of Object.entries(layouts)) {
      if (Array.isArray(items)) {
        const filtered = items
          .filter((item: { i: string }) => activeKeys.has(item.i))
          .sort((a: { y: number; x: number }, b: { y: number; x: number }) => a.y - b.y || a.x - b.x)

        // Re-compact: for each item, find the earliest y it can fit without overlapping
        const placed: { x: number; y: number; w: number; h: number }[] = []
        result[bp] = filtered.map((item: { i: string; x: number; y: number; w: number; h: number }) => {
          let newY = 0
          for (const p of placed) {
            // Check if they overlap on x-axis
            if (item.x < p.x + p.w && item.x + item.w > p.x) {
              newY = Math.max(newY, p.y + p.h)
            }
          }
          const compacted = { ...item, y: newY }
          placed.push(compacted)
          return compacted
        })
      }
    }
    return result as typeof layouts
  }, [layouts, activeWidgets])

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
          rowHeight={30}
          onLayoutChange={onLayoutChange}
          dragConfig={{
            enabled: true,
            handle: '.drag-handle',
          }}
          resizeConfig={{
            enabled: true,
          }}
          containerPadding={[0, 0] as const}
          margin={[16, 16] as const}
        >
          {activeWidgets.map((w) => (
            <div key={w.key} className="h-full relative group overflow-hidden rounded-xl">
              <div className="drag-handle absolute top-0 left-0 right-0 h-6 cursor-grab active:cursor-grabbing z-10 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                <div className="w-8 h-1 rounded-full bg-border" />
              </div>
              <div className="h-full">{widgetContent[w.key]}</div>
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
