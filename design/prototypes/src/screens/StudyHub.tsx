import { CalendarDays, Check } from 'lucide-react'
import { Card, Badge, Button, SkeletonRows, EmptyState, ErrorState, SectionLabel } from '../ui'
import { PageShell, SyncChip } from './shared'
import { useSim } from '../lib/sim'
import { planner, flashcards } from '../lib/mock'

const TABS = ['Plan', 'Flashcards', 'Timed', 'Exams', 'History']

export function StudyHub() {
  const { sim } = useSim()

  return (
    <PageShell
      title="Study"
      subtitle="Plan the week, then work the queue"
      actions={sim === 'offline' ? <SyncChip count={2} /> : <Button size="sm" kbd="S">Start session</Button>}
      wide
    >
      {/* tabs */}
      <div className="flex items-center gap-1 border-b border-border mb-6" role="tablist">
        {TABS.map((t, i) => (
          <button
            key={t}
            role="tab"
            aria-selected={i === 0}
            className={`text-[13px] px-3.5 py-2 -mb-px cursor-pointer ${
              i === 0 ? 'text-text font-medium border-b-2 border-sage' : 'text-text-muted hover:text-text'
            }`}
          >
            {t}
            {t === 'Plan' && <Badge tone="sage" className="ml-1.5">new</Badge>}
          </button>
        ))}
        <span className="ml-auto text-[10px] font-mono text-text-faint pb-2">1–5 switch tabs</span>
      </div>

      {sim === 'loading' && (
        <div className="grid grid-cols-2 gap-4">
          <Card><SkeletonRows rows={5} /></Card>
          <Card><SkeletonRows rows={5} /></Card>
        </div>
      )}
      {sim === 'empty' && (
        <EmptyState
          title="Nothing scheduled this week"
          hint="Add an exam with a date and the planner builds a daily card schedule from your readiness."
          action={<Button size="sm">Create an exam</Button>}
        />
      )}
      {sim === 'error' && (
        <ErrorState title="The weekly plan couldn't load" detail="GET /api/study/schedule → 503" onRetry={() => {}} />
      )}

      {(sim === 'default' || sim === 'offline') && (
        <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
          {/* Plan tab content — the weekly planner */}
          <div className="lg:col-span-3">
            <SectionLabel>This week — built from CSIT302 (9d out) &amp; CSCI368 (21d out)</SectionLabel>
            <Card dense>
              <ul className="divide-y divide-border">
                {planner.map((d) => {
                  const today = d.day === 'Fri'
                  return (
                    <li key={d.day} className={`flex items-center gap-4 py-2 px-1 ${today ? 'bg-sage-soft -mx-3 px-4 rounded-lg' : ''}`}>
                      <span className={`font-mono text-[11px] w-8 shrink-0 ${today ? 'text-sage-fg font-semibold' : 'text-text-faint'}`}>
                        {d.day}
                      </span>
                      <div className="flex flex-wrap items-center gap-2 flex-1">
                        {d.items.map((it, i) => (
                          <span
                            key={i}
                            className={`inline-flex items-center gap-1.5 text-xs rounded-md px-2 py-1 ${
                              it.done ? 'bg-surface-2 text-text-faint line-through' : 'bg-surface-2 text-text'
                            }`}
                          >
                            {it.done && <Check size={11} className="text-sage-fg" />}
                            <span className="font-mono text-[10px] text-text-faint no-underline">{it.course}</span>
                            {it.what}
                          </span>
                        ))}
                      </div>
                      {today && <Button size="sm">Start</Button>}
                    </li>
                  )
                })}
              </ul>
              <div className="flex items-center justify-between mt-3 pt-3 border-t border-border text-[11px] text-text-faint">
                <span className="flex items-center gap-1.5">
                  <CalendarDays size={11} /> targets scale with exam urgency — CSIT302 gets 2× this week
                </span>
                <button className="hover:text-text-muted cursor-pointer underline underline-offset-2">rebuild plan</button>
              </div>
            </Card>
          </div>

          {/* Flashcard preview (what a session looks like) */}
          <div className="lg:col-span-2">
            <SectionLabel>Session preview — card 7 of 20</SectionLabel>
            <Card className="flex flex-col">
              <div className="flex items-center justify-between mb-4">
                <Badge tone="muted">{flashcards[0].course} · wk {flashcards[0].week}</Badge>
                <div className="h-1 w-24 bg-surface-2 rounded-full overflow-hidden">
                  <div className="h-full w-1/3 bg-sage rounded-full" />
                </div>
              </div>
              <p className="text-[15px] font-medium leading-relaxed flex-1">{flashcards[0].front}</p>
              <div className="text-center text-[11px] text-text-faint font-mono my-5">
                <kbd>space</kbd> reveal answer
              </div>
              <div className="grid grid-cols-4 gap-1.5" aria-label="Rate recall">
                {[
                  ['Again', 'bg-red-soft text-red-fg', '1'],
                  ['Hard', 'bg-amber-soft text-amber-fg', '2'],
                  ['Good', 'bg-sage-soft text-sage-fg', '3'],
                  ['Easy', 'bg-peri-soft text-peri-fg', '4'],
                ].map(([label, cls, key]) => (
                  <button
                    key={label}
                    className={`text-xs font-medium rounded-lg py-2 cursor-pointer transition-opacity hover:opacity-80 ${cls}`}
                  >
                    {label}
                    <span className="block font-mono text-[9px] opacity-70 mt-0.5">{key}</span>
                  </button>
                ))}
              </div>
            </Card>
          </div>
        </div>
      )}
    </PageShell>
  )
}
