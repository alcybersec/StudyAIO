import { GripVertical, Flame, Upload, Settings2 } from 'lucide-react'
import { Card, Badge, Button, Skeleton, SkeletonRows, EmptyState, ErrorState, SectionLabel } from '../ui'
import { PageShell } from './shared'
import { useSim } from '../lib/sim'
import { courses, exams, deadlines, activity } from '../lib/mock'

/** One widget = one isolated data region: it loads, empties, and fails alone. */
function Widget({
  title,
  span = 1,
  children,
  state = 'default',
  emptyTitle,
  emptyHint,
}: {
  title: string
  span?: 1 | 2
  children: React.ReactNode
  state?: 'default' | 'loading' | 'empty' | 'error'
  emptyTitle?: string
  emptyHint?: string
}) {
  return (
    <Card dense className={`relative group ${span === 2 ? 'md:col-span-2' : ''}`}>
      <span className="absolute top-2.5 right-2.5 text-text-faint opacity-0 group-hover:opacity-100 cursor-grab transition-opacity" aria-hidden>
        <GripVertical size={13} />
      </span>
      <SectionLabel>{title}</SectionLabel>
      {state === 'loading' && <SkeletonRows rows={3} />}
      {state === 'empty' && <EmptyState title={emptyTitle ?? 'Nothing here yet'} hint={emptyHint} />}
      {state === 'error' && <ErrorState compact title={`${title} couldn't load`} detail="GET /api/dashboard → 502 Bad Gateway" onRetry={() => {}} />}
      {state === 'default' && children}
    </Card>
  )
}

export function Home() {
  const { sim } = useSim()
  // In 'error' sim, ONE widget fails while the rest stay healthy — that's the point.
  const w = (normal: 'default' | 'loading' | 'empty') => (sim === 'loading' ? 'loading' : sim === 'empty' ? 'empty' : normal)

  return (
    <PageShell
      title="Home"
      subtitle={
        <>
          Friday, July 4 · Week 9 ·{' '}
          <span className="text-amber-fg font-semibold inline-flex items-center gap-1">
            <Flame size={11} /> 12-day streak
          </span>
        </>
      }
      actions={
        <>
          <Button variant="ghost" size="sm">
            <Settings2 size={13} /> Customize
          </Button>
          <Button size="sm" kbd="S">
            Start session
          </Button>
        </>
      }
      wide
    >
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
        {/* Streak */}
        <Widget title="Streak" state={w('default')} emptyTitle="No sessions yet" emptyHint="Review a few cards to start a streak.">
          <div className="text-2xl font-bold text-amber-fg">12 days</div>
          <div className="flex items-end gap-1 mt-3 h-7" aria-hidden>
            {[14, 22, 10, 26, 18, 24, 6].map((h, i) => (
              <div key={i} className={`w-2.5 rounded-sm ${i === 6 ? 'bg-surface-2' : i % 2 ? 'bg-amber/60' : 'bg-amber'}`} style={{ height: h }} />
            ))}
          </div>
          <div className="text-[11px] text-text-faint mt-2">18 cards today keeps it alive</div>
        </Widget>

        {/* Exams */}
        <Widget title="Active exams" span={2} state={sim === 'error' ? 'error' : w('default')} emptyTitle="No exams tracked" emptyHint="Create one from Study → Exams.">
          <div className="grid grid-cols-2 gap-2.5">
            {exams.map((e) => (
              <div key={e.id} className="bg-surface-2 rounded-lg p-3">
                <div className="flex items-center justify-between">
                  <span className="text-[13px] font-semibold">{e.title}</span>
                  <Badge tone={e.daysLeft <= 10 ? 'red' : 'muted'}>{e.daysLeft}d</Badge>
                </div>
                <div className="h-1 bg-surface-0 rounded-full mt-2.5 overflow-hidden">
                  <div className={`h-full rounded-full ${e.readiness >= 60 ? 'bg-sage' : 'bg-amber'}`} style={{ width: `${e.readiness}%` }} />
                </div>
                <div className="text-[11px] text-text-muted mt-1.5">
                  readiness <span className="font-medium text-text">{e.readiness}%</span> · <button className="underline decoration-border-strong underline-offset-2 hover:text-text cursor-pointer">why?</button>
                </div>
              </div>
            ))}
          </div>
        </Widget>

        {/* XP */}
        <Widget title="Level 7 · 2,340 XP" state={w('default')}>
          <div className="h-1.5 bg-surface-2 rounded-full overflow-hidden mt-1">
            <div className="h-full bg-peri rounded-full" style={{ width: '62%' }} />
          </div>
          <div className="text-[11px] text-text-faint mt-2">460 XP to level 8</div>
          <div className="text-xs mt-3 flex items-center gap-1.5">
            <Badge tone="peri">new</Badge> Consistency III unlocked
          </div>
        </Widget>

        {/* Deadlines */}
        <Widget title="Upcoming deadlines" span={2} state={w('default')} emptyTitle="No deadlines" emptyHint="Import a course outline in Course Ops to track deadlines.">
          <ul className="text-[13px] divide-y divide-border">
            {deadlines.map((d, i) => (
              <li key={i} className="flex items-center justify-between py-1.5">
                <span className="flex items-center gap-2 min-w-0">
                  <span className="font-mono text-[10px] text-text-faint shrink-0">{d.course}</span>
                  <span className="truncate">{d.title}</span>
                </span>
                <span className={`text-xs font-semibold shrink-0 ml-3 ${d.urgency === 'red' ? 'text-red-fg' : d.urgency === 'amber' ? 'text-amber-fg' : 'text-text-faint'}`}>
                  {d.due}
                </span>
              </li>
            ))}
          </ul>
        </Widget>

        {/* Activity */}
        <Widget title="Recent activity" span={2} state={w('default')} emptyTitle="No activity yet">
          <ul className="text-xs text-text-muted space-y-2">
            {activity.map((a, i) => (
              <li key={i} className="flex justify-between gap-3">
                <span className="truncate">{a.text}</span>
                <span className="text-text-faint font-mono text-[10px] shrink-0">{a.when}</span>
              </li>
            ))}
          </ul>
        </Widget>

        {/* Courses */}
        <Widget title="Courses" span={2} state={w('default')} emptyTitle="No courses yet" emptyHint="Upload your first lecture and a course is created automatically.">
          <div className="grid grid-cols-3 gap-2.5">
            {courses.map((c) => (
              <button key={c.code} className="bg-surface-2 hover:bg-surface-0 border border-transparent hover:border-border rounded-lg p-3 text-left cursor-pointer transition-colors">
                <div className="text-[13px] font-semibold">{c.code}</div>
                <div className="text-[11px] text-text-muted truncate">{c.name}</div>
                <div className="text-[10px] text-text-faint font-mono mt-1.5">{c.weeks} wks · {c.cards} cards</div>
              </button>
            ))}
          </div>
        </Widget>

        {/* Upload */}
        <Widget title="Quick upload" span={2} state={w('default')}>
          <button className="w-full border border-dashed border-border-strong rounded-lg py-6 text-xs text-text-muted hover:text-text hover:border-text-faint transition-colors flex items-center justify-center gap-2 cursor-pointer">
            <Upload size={14} /> Drop lecture files or click — PDF, DOCX, PPTX
          </button>
        </Widget>
      </div>

      {sim === 'error' && (
        <p className="text-[11px] text-text-faint mt-4 font-mono">
          ↑ note: only the exams widget failed — every other widget keeps working. That's the per-widget error isolation standard.
        </p>
      )}
    </PageShell>
  )
}
