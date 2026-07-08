import { Plus, SendHorizonal, X, WifiOff } from 'lucide-react'
import { Button, Badge, Skeleton, EmptyState, ErrorState } from '../ui'
import { useSim } from '../lib/sim'
import { chatSessions, chatMessages } from '../lib/mock'

function SessionRail() {
  return (
    <aside className="w-60 shrink-0 border-r border-border bg-surface-1 flex flex-col">
      <div className="p-3">
        <Button variant="secondary" size="sm" className="w-full" kbd="⌘N">
          <Plus size={13} /> New question
        </Button>
      </div>
      <div className="px-3 pb-2 text-[10px] font-mono uppercase tracking-[0.12em] text-text-faint">Sessions</div>
      <div className="flex-1 overflow-y-auto px-2 pb-3 space-y-0.5">
        {chatSessions.map((s, i) => (
          <button
            key={s.id}
            className={`w-full text-left px-2.5 py-2 rounded-lg cursor-pointer ${i === 0 ? 'bg-surface-2' : 'hover:bg-surface-2'}`}
          >
            <div className={`text-[13px] truncate ${i === 0 ? 'text-text font-medium' : 'text-text-muted'}`}>{s.title}</div>
            <div className="text-[10px] text-text-faint font-mono mt-0.5">{s.when} · {s.count} msgs</div>
          </button>
        ))}
      </div>
    </aside>
  )
}

function Composer() {
  return (
    <div className="border-t border-border bg-surface-1 p-4">
      <div className="flex items-center gap-1.5 mb-2.5">
        <Badge tone="sage">
          CSIT302 <X size={10} className="cursor-pointer" />
        </Badge>
        <Badge tone="sage">
          Week 7–9 <X size={10} className="cursor-pointer" />
        </Badge>
        <button className="text-[11px] text-text-faint hover:text-text-muted cursor-pointer">+ scope</button>
      </div>
      <div className="flex items-end gap-2">
        <div className="flex-1 bg-surface-0 border border-border rounded-xl px-4 py-3 text-sm text-text-faint">
          Ask anything about your lectures…
        </div>
        <Button size="md" aria-label="Send" kbd="↵">
          <SendHorizonal size={14} />
        </Button>
      </div>
      <div className="text-[10px] text-text-faint font-mono mt-2">answers cite their source weeks · scope chips narrow retrieval</div>
    </div>
  )
}

export function Ask() {
  const { sim } = useSim()

  return (
    <div className="flex h-full">
      <SessionRail />
      <div className="flex-1 flex flex-col min-w-0">
        <div className="flex-1 overflow-y-auto px-6 py-6 space-y-5 max-w-3xl w-full mx-auto">
          {sim === 'loading' && (
            <>
              <Skeleton className="h-10 w-2/3 ml-auto rounded-xl" />
              <Skeleton className="h-32 w-full rounded-xl" />
            </>
          )}
          {sim === 'empty' && (
            <EmptyState
              title="Ask your first question"
              hint="Answers come from your own lecture material, with citations. Scope to a course or week for sharper retrieval."
              action={<Button size="sm">Try: “summarize week 9 in 5 bullets”</Button>}
            />
          )}
          {sim === 'error' && (
            <ErrorState
              title="Couldn't load this conversation"
              detail="GET /api/chat/sessions/s1/messages → 500"
              onRetry={() => {}}
            />
          )}
          {(sim === 'default' || sim === 'offline') && (
            <>
              {/* user message */}
              <div className="flex justify-end">
                <div className="bg-surface-2 rounded-xl rounded-br-sm px-4 py-2.5 text-sm max-w-md">{chatMessages[0].text}</div>
              </div>

              {/* assistant, streaming */}
              <div className="max-w-2xl">
                <div className="text-sm leading-relaxed whitespace-pre-wrap">
                  {chatMessages[1].text}
                  <span className="inline-block w-1.5 h-4 bg-peri ml-0.5 animate-pulse align-text-bottom" aria-hidden />
                </div>
                <div className="flex items-center gap-1.5 mt-3">
                  {chatMessages[1].sources?.map((s) => (
                    <button key={s} className="text-[11px] bg-peri-soft text-peri-fg rounded-md px-2 py-1 hover:opacity-80 cursor-pointer">
                      {s}
                    </button>
                  ))}
                </div>
              </div>

              {sim === 'offline' && (
                <div className="flex items-center gap-2.5 border border-amber/25 bg-amber-soft rounded-lg px-3.5 py-2.5 text-xs text-amber-fg max-w-md" role="alert">
                  <WifiOff size={13} />
                  Stream interrupted — reconnecting (attempt 2)…
                  <Button variant="secondary" size="sm" className="ml-auto">Resume now</Button>
                </div>
              )}
            </>
          )}
        </div>
        <Composer />
      </div>
    </div>
  )
}
