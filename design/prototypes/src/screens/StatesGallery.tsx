import { CheckCircle2, XCircle, Keyboard } from 'lucide-react'
import { Card, Button, EmptyState, ErrorState, SectionLabel } from '../ui'
import { OfflineBanner, SyncChip } from './shared'

function Toast({ tone, children }: { tone: 'success' | 'error'; children: React.ReactNode }) {
  return (
    <div
      role="status"
      className={`flex items-center gap-2.5 rounded-xl border px-4 py-3 text-[13px] bg-surface-1 shadow-lg shadow-black/10 max-w-sm ${
        tone === 'success' ? 'border-sage/30' : 'border-red/30'
      }`}
    >
      {tone === 'success' ? <CheckCircle2 size={15} className="text-sage-fg shrink-0" /> : <XCircle size={15} className="text-red-fg shrink-0" />}
      <span className="flex-1">{children}</span>
      {tone === 'error' && <Button variant="secondary" size="sm">Retry</Button>}
    </div>
  )
}

const shortcuts = [
  ['⌘K', 'command palette'], ['S', 'start session'], ['U', 'upload'], ['?', 'this overlay'],
  ['g h', 'go home'], ['g s', 'go study'], ['j / k', 'next / prev row'], ['a e d', 'triage inbox'],
  ['space', 'reveal card'], ['1–4', 'rate recall'],
]

export function StatesGallery() {
  return (
    <div className="max-w-4xl mx-auto px-6 py-8 space-y-10">
      <div>
        <h1 className="text-xl font-bold tracking-tight mb-1">States &amp; errors</h1>
        <p className="text-xs text-text-muted">The four-state standard + the error surfaces, side by side</p>
      </div>

      <section>
        <SectionLabel>Empty — always says what this is and how to fill it</SectionLabel>
        <Card>
          <EmptyState
            title="No flashcards for this week yet"
            hint="Cards are generated automatically when a lecture finishes processing — or add your own."
            action={<Button size="sm" variant="secondary">Generate now</Button>}
          />
        </Card>
      </section>

      <section>
        <SectionLabel>Inline query error — in place of the content, shell stays alive</SectionLabel>
        <ErrorState
          title="Analytics couldn't load"
          detail="GET /api/analytics/overview → 502 Bad Gateway · request-id 4f21c9"
          onRetry={() => {}}
        />
      </section>

      <section>
        <SectionLabel>Mutation toasts — same verb start to finish</SectionLabel>
        <div className="space-y-2.5">
          <Toast tone="success">Exam archived</Toast>
          <Toast tone="error">Couldn't archive the exam — it's still active</Toast>
        </div>
      </section>

      <section>
        <SectionLabel>Study writes never die — retry queue chip (offline OR server error)</SectionLabel>
        <Card dense className="flex items-center justify-between">
          <span className="text-[13px] text-text-muted">Session finished · 18 cards · 89% correct</span>
          <SyncChip count={3} />
        </Card>
        <p className="text-[11px] text-text-faint mt-2">
          Reviews, quiz attempts and session records queue in IndexedDB on any failure and replay automatically. The chip disappears when flushed; a toast confirms.
        </p>
      </section>

      <section>
        <SectionLabel>Connectivity — one global banner, all pages</SectionLabel>
        <OfflineBanner />
      </section>

      <section>
        <SectionLabel>Rate limited — 429 gets a countdown, not a mystery</SectionLabel>
        <Card dense className="flex items-center justify-between max-w-md">
          <span className="text-[13px] text-amber-fg">AI provider rate limit reached</span>
          <span className="font-mono text-xs text-text-muted">retry in 0:42</span>
        </Card>
      </section>

      <section>
        <SectionLabel>Shortcut overlay — “?” anywhere</SectionLabel>
        <div className="bg-surface-1 border border-border-strong rounded-xl shadow-2xl shadow-black/20 max-w-md p-5">
          <div className="flex items-center gap-2 mb-4">
            <Keyboard size={15} className="text-text-faint" />
            <span className="text-sm font-semibold">Keyboard shortcuts</span>
            <kbd className="ml-auto">esc</kbd>
          </div>
          <div className="grid grid-cols-2 gap-x-8 gap-y-2">
            {shortcuts.map(([k, label]) => (
              <div key={k} className="flex items-center justify-between text-[13px]">
                <span className="text-text-muted">{label}</span>
                <kbd>{k}</kbd>
              </div>
            ))}
          </div>
        </div>
      </section>
    </div>
  )
}
