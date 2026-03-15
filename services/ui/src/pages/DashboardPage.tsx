import { useMemo, useState } from 'react'
import { ResponsiveGridLayout, useContainerWidth } from 'react-grid-layout'
import 'react-grid-layout/css/styles.css'
import 'react-resizable/css/styles.css'
import { useDashboard } from '../hooks/useApi'
import { useDashboardLayout } from '../hooks/useDashboardLayout'
import { LoadingSpinner, ErrorBanner, PageHeader, EmptyState } from '../components/ui'
import { ReviewAlert } from '../components/dashboard/ReviewAlert'
import { ActivityFeed } from '../components/dashboard/ActivityFeed'
import { CourseCard } from '../components/dashboard/CourseCard'
import { ExamCountdown } from '../components/dashboard/ExamCountdown'
import { QuickUpload } from '../components/dashboard/QuickUpload'
import { StreakDisplay } from '../components/dashboard/StreakDisplay'
import { StudyProgress } from '../components/dashboard/StudyProgress'
import { GamificationWidget } from '../components/gamification/GamificationWidget'
import { AchievementUnlock } from '../components/gamification/AchievementUnlock'
import { InstallPrompt } from '../components/pwa/InstallPrompt'
import { DashboardCustomizer } from '../components/dashboard/DashboardCustomizer'

function DeadlinesWidget({ deadlines, now }: { deadlines: { id: string; title: string; due_date: string; course_code: string; is_confirmed: boolean }[]; now: number }) {
  return (
    <div className="h-full rounded-lg border border-border bg-surface p-4 overflow-auto">
      <h3 className="mb-3 text-sm font-semibold text-text">Upcoming Deadlines</h3>
      <div className="space-y-2">
        {deadlines.map((d) => {
          const days = Math.ceil((new Date(d.due_date).getTime() - now) / (1000 * 60 * 60 * 24))
          return (
            <div key={d.id} className="flex items-center justify-between text-sm">
              <div className="flex items-center gap-2">
                <span className="inline-flex rounded bg-surface-alt px-1.5 py-0.5 text-xs font-medium text-text-muted">
                  {d.course_code}
                </span>
                <span className="text-text">{d.title}</span>
                {!d.is_confirmed && <span className="text-xs text-yellow-600">(unconfirmed)</span>}
              </div>
              <span className={`text-xs ${days <= 3 ? 'font-medium text-red-600' : days <= 7 ? 'text-yellow-600' : 'text-text-muted'}`}>
                {d.due_date} ({days <= 0 ? 'Today' : `${days}d`})
              </span>
            </div>
          )
        })}
      </div>
    </div>
  )
}

export function DashboardPage() {
  const { data, isLoading, error, refetch } = useDashboard()
  const now = useMemo(() => Date.now(), []) // eslint-disable-line react-hooks/purity
  const { layouts, hiddenWidgets, visibleWidgets, onLayoutChange, toggleWidget, resetLayout } = useDashboardLayout()
  const [customizerOpen, setCustomizerOpen] = useState(false)
  const { width, containerRef } = useContainerWidth()

  if (isLoading) return <LoadingSpinner label="Loading dashboard..." />
  if (error) return <ErrorBanner message="Failed to load dashboard. Check that the API server is running." onRetry={refetch} />

  if (!data) return null

  const isVisible = (key: string) => visibleWidgets.some((w) => w.key === key)

  const widgetContent: Record<string, React.ReactNode | null> = {
    streak: data.streak ? <StreakDisplay streak={data.streak} /> : null,
    exams: data.active_exams?.length ? <ExamCountdown exams={data.active_exams} /> : null,
    gamification: data.gamification ? <GamificationWidget gamification={data.gamification} /> : null,
    study: data.study_stats && data.study_stats.total > 0 ? <StudyProgress stats={data.study_stats} /> : null,
    deadlines: data.upcoming_deadlines?.length ? <DeadlinesWidget deadlines={data.upcoming_deadlines} now={now} /> : null,
    activity: <ActivityFeed items={data.recent_activity} />,
    upload: <QuickUpload />,
    courses: data.courses.length > 0 ? (
      <div className="h-full overflow-auto">
        <h2 className="text-sm font-semibold text-text mb-4">Your Courses</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {data.courses.map((course) => (
            <CourseCard key={course.id} course={course} />
          ))}
        </div>
      </div>
    ) : (
      <EmptyState
        title="No courses yet"
        description="Upload your first lecture file to get started."
        actionLabel="Upload"
        actionTo="/upload"
      />
    ),
  }

  // Filter to only visible widgets that have content
  const activeWidgets = visibleWidgets.filter((w) => isVisible(w.key) && widgetContent[w.key] !== null)
  const activeKeys = new Set(activeWidgets.map((w) => w.key))

  // Filter layouts to only include active widgets and re-compact vertically
  const filteredLayouts = useMemo(() => {
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
          // Find the lowest y where this item fits
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
  }, [layouts, activeKeys]) // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div ref={containerRef}>
      <div className="flex items-center justify-between mb-2">
        <PageHeader title="Dashboard" subtitle={`${data.courses.length} course${data.courses.length !== 1 ? 's' : ''} tracked`} />
        <button
          onClick={() => setCustomizerOpen(true)}
          aria-label="Customize dashboard"
          className="text-sm px-3 py-1.5 rounded-lg border border-border text-text-muted hover:text-text hover:bg-surface-alt transition-colors"
        >
          Customize
        </button>
      </div>

      <ReviewAlert count={data.pending_review_count} />

      <ResponsiveGridLayout
        className="layout"
        width={width ?? 1200}
        layouts={filteredLayouts}
        breakpoints={{ lg: 1024, sm: 0 }}
        cols={{ lg: 12, sm: 12 }}
        rowHeight={30}
        onLayoutChange={onLayoutChange}
        dragConfig={{
          enabled: window.innerWidth >= 1024,
          handle: '.drag-handle',
        }}
        resizeConfig={{
          enabled: window.innerWidth >= 1024,
        }}
        containerPadding={[0, 0] as const}
        margin={[16, 16] as const}
      >
        {activeWidgets.map((w) => (
          <div key={w.key} className="relative group overflow-hidden rounded-lg">
            <div className="drag-handle absolute top-0 left-0 right-0 h-6 cursor-grab active:cursor-grabbing z-10 opacity-0 group-hover:opacity-100 transition-opacity hidden lg:flex items-center justify-center">
              <div className="w-8 h-1 rounded-full bg-border" />
            </div>
            <div className="h-full">{widgetContent[w.key]}</div>
          </div>
        ))}
      </ResponsiveGridLayout>

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
