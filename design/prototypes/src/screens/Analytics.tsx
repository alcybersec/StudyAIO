import { BarChart3, ArrowRight } from 'lucide-react'
import { Card, Button, Skeleton, EmptyState, ErrorState, SectionLabel } from '../ui'
import { PageShell } from './shared'
import { useSim } from '../lib/sim'
import { weakTopics } from '../lib/mock'

/* ------------------------------------------------------------- stat cards */

interface Stat {
  label: string
  value: string
  trend: number[]
  tone: string // CSS var for the sparkline
}

const stats: Stat[] = [
  { label: 'Cards reviewed', value: '1,284', trend: [4, 7, 6, 9, 8, 12, 11, 14], tone: 'var(--t-sage)' },
  { label: 'Avg accuracy', value: '84%', trend: [10, 9, 11, 8, 12, 11, 13, 12], tone: 'var(--t-peri)' },
  { label: 'Study time', value: '42h', trend: [3, 5, 4, 7, 6, 9, 8, 11], tone: 'var(--t-amber)' },
  { label: 'Streak', value: '12d', trend: [2, 4, 6, 7, 9, 10, 12, 14], tone: 'var(--t-sage)' },
]

function Sparkline({ trend, tone }: { trend: number[]; tone: string }) {
  const max = Math.max(...trend)
  const points = trend.map((v, i) => `${(i / (trend.length - 1)) * 64},${18 - (v / max) * 16}`).join(' ')
  return (
    <svg viewBox="0 0 64 20" className="w-16 h-5" aria-hidden>
      <polyline points={points} fill="none" style={{ stroke: tone }} strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

/* ---------------------------------------------------------------- heatmap */

const MONTHS = ['Mar', 'Apr', 'May', 'Jun', 'Jul']
const WEEKS = 16
const DAYS = 7

/** Deterministic pseudo-random intensity 0–4 so the grid looks organic but stable. */
function intensity(day: number, week: number): number {
  const h = (day * 31 + week * 17 + ((day * week) % 11)) % 9
  return h < 2 ? 0 : h < 4 ? 1 : h < 6 ? 2 : h < 8 ? 3 : 4
}

const LEVEL_OPACITY = [0, 0.25, 0.45, 0.7, 1]

function Heatmap() {
  return (
    <div>
      <div className="flex gap-6 font-mono text-[10px] text-text-faint mb-1.5 pl-0.5" aria-hidden>
        {MONTHS.map((m) => (
          <span key={m}>{m}</span>
        ))}
      </div>
      <div className="flex gap-[3px]" role="img" aria-label="Study activity heatmap — last 16 weeks">
        {Array.from({ length: WEEKS }).map((_, w) => (
          <div key={w} className="flex flex-col gap-[3px]">
            {Array.from({ length: DAYS }).map((_, d) => {
              const lvl = intensity(d, w)
              return lvl === 0 ? (
                <div key={d} className="w-3 h-3 rounded-[3px] bg-surface-2" />
              ) : (
                <div key={d} className="w-3 h-3 rounded-[3px]" style={{ background: 'var(--t-sage)', opacity: LEVEL_OPACITY[lvl] }} />
              )
            })}
          </div>
        ))}
      </div>
      <div className="flex items-center gap-1.5 mt-2.5 font-mono text-[10px] text-text-faint">
        less
        <span className="w-3 h-3 rounded-[3px] bg-surface-2 inline-block" />
        {LEVEL_OPACITY.slice(1).map((o) => (
          <span key={o} className="w-3 h-3 rounded-[3px] inline-block" style={{ background: 'var(--t-sage)', opacity: o }} />
        ))}
        more
      </div>
    </div>
  )
}

/* ------------------------------------------------------------- readiness */

interface TopicRow {
  topic: string
  course: string
  week: number
  accuracy: number
}

const strongTopics: TopicRow[] = [
  { topic: 'Stack canaries', course: 'CSIT302', week: 7, accuracy: 88 },
  { topic: 'Network scanning', course: 'CSIT302', week: 4, accuracy: 91 },
  { topic: 'SQL injection', course: 'CSIT302', week: 5, accuracy: 86 },
]

const topicRows: TopicRow[] = [...weakTopics, ...strongTopics].sort((a, b) => a.accuracy - b.accuracy)

function accuracyVar(pct: number): string {
  return pct < 60 ? 'var(--t-red)' : pct < 70 ? 'var(--t-amber)' : 'var(--t-sage)'
}

function ReadinessCard() {
  return (
    <Card dense>
      <div className="flex items-center justify-between gap-3">
        <SectionLabel>Exam readiness — CSIT302 Final · 68%</SectionLabel>
        <span className="font-mono text-[10px] text-text-faint shrink-0">9 days out</span>
      </div>
      <div className="h-1.5 bg-surface-2 rounded-full overflow-hidden mb-3">
        <div className="h-full bg-sage rounded-full" style={{ width: '68%' }} />
      </div>

      <div className="divide-y divide-border" role="table" aria-label="Per-topic mastery">
        {topicRows.map((t) => {
          const weak = t.accuracy < 70
          return (
            <div key={t.topic} className="flex items-center gap-3 py-2 text-[13px] hover:bg-surface-2/50 rounded-sm cursor-pointer transition-colors" role="row">
              <span className="flex-1 min-w-0 truncate font-medium">{t.topic}</span>
              <span className="font-mono text-[10px] text-text-faint w-10 shrink-0">wk {t.week}</span>
              <span className="w-24 h-1 bg-surface-2 rounded-full overflow-hidden shrink-0" aria-hidden>
                <span className="block h-full rounded-full" style={{ width: `${t.accuracy}%`, background: accuracyVar(t.accuracy) }} />
              </span>
              <span
                className="font-mono text-xs w-9 text-right shrink-0"
                style={{ color: weak ? (t.accuracy < 60 ? 'var(--t-red-fg)' : 'var(--t-amber-fg)') : 'var(--t-text-muted)' }}
              >
                {t.accuracy}%
              </span>
              <span className="w-24 shrink-0 text-right">
                {weak && (
                  <Button variant="ghost" size="sm">
                    Study now <ArrowRight size={12} />
                  </Button>
                )}
              </span>
            </div>
          )
        })}
      </div>

      <p className="font-mono text-[11px] text-text-faint mt-3">
        readiness = weighted topic mastery × coverage · click any row to scope a session
      </p>
    </Card>
  )
}

/* ---------------------------------------------------------------- screen */

export function Analytics() {
  const { sim } = useSim()

  return (
    <PageShell title="Analytics" subtitle="What you've studied, how well it stuck, and where the exam risk lives." wide>
      {sim === 'loading' ? (
        <div className="space-y-4">
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            {Array.from({ length: 4 }).map((_, i) => (
              <Card dense key={i}>
                <Skeleton className="h-3 w-20 mb-2" />
                <Skeleton className="h-7 w-16 mb-2" />
                <Skeleton className="h-5 w-16" />
              </Card>
            ))}
          </div>
          <Card dense>
            <Skeleton className="h-3 w-24 mb-3" />
            <Skeleton className="h-[110px] w-full" />
          </Card>
          <Card dense>
            <Skeleton className="h-3 w-48 mb-3" />
            <div className="space-y-2.5">
              {Array.from({ length: 6 }).map((_, i) => (
                <Skeleton key={i} className="h-5 w-full" />
              ))}
            </div>
          </Card>
        </div>
      ) : sim === 'empty' ? (
        <Card>
          <EmptyState
            icon={<BarChart3 size={28} strokeWidth={1.5} />}
            title="No study data yet"
            hint="Analytics appear after your first review session. Ten cards is enough to start the picture."
            action={<Button size="sm">Start a session</Button>}
          />
        </Card>
      ) : sim === 'error' ? (
        <ErrorState title="Analytics couldn't load" detail="GET /api/analytics → 500 Internal Server Error" onRetry={() => {}} />
      ) : (
        <div className="space-y-4">
          {/* Row 1 — stats */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            {stats.map((s) => (
              <Card dense key={s.label}>
                <SectionLabel>{s.label}</SectionLabel>
                <div className="flex items-end justify-between gap-2">
                  <span className="text-2xl font-bold tracking-tight">{s.value}</span>
                  <Sparkline trend={s.trend} tone={s.tone} />
                </div>
              </Card>
            ))}
          </div>

          {/* Row 2 — heatmap */}
          <Card dense>
            <SectionLabel>Study heatmap</SectionLabel>
            <Heatmap />
          </Card>

          {/* Row 3 — readiness drill-down */}
          <ReadinessCard />
        </div>
      )}
    </PageShell>
  )
}
