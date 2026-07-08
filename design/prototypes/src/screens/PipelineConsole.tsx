import { Check, Loader2, X, Clock, Upload, RotateCcw, ClipboardPaste } from 'lucide-react'
import { Card, Badge, Button, Skeleton, EmptyState, ErrorState, SectionLabel } from '../ui'
import { PageShell } from './shared'
import { useSim } from '../lib/sim'
import { pipelineFiles } from '../lib/mock'

function StageDot({ status }: { status: string }) {
  if (status === 'done')
    return (
      <span className="w-5 h-5 rounded-full bg-sage-soft text-sage-fg flex items-center justify-center shrink-0">
        <Check size={11} strokeWidth={3} />
      </span>
    )
  if (status === 'running')
    return (
      <span className="w-5 h-5 rounded-full bg-peri-soft text-peri-fg flex items-center justify-center shrink-0">
        <Loader2 size={11} className="animate-spin" />
      </span>
    )
  if (status === 'failed')
    return (
      <span className="w-5 h-5 rounded-full bg-red-soft text-red-fg flex items-center justify-center shrink-0">
        <X size={11} strokeWidth={3} />
      </span>
    )
  return (
    <span className="w-5 h-5 rounded-full bg-surface-2 text-text-faint flex items-center justify-center shrink-0">
      <Clock size={10} />
    </span>
  )
}

function FileRow({ file }: { file: (typeof pipelineFiles)[number] }) {
  const failed = file.stages.find((s) => s.status === 'failed')
  return (
    <Card dense className="mb-3">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2.5 min-w-0">
          <span className="font-mono text-[13px] font-medium truncate">{file.name}</span>
          <span className="text-[11px] text-text-faint shrink-0">{file.size}</span>
        </div>
        {failed ? <Badge tone="red">failed at {failed.name.toLowerCase()}</Badge> : <Badge tone="peri">processing</Badge>}
      </div>

      {/* stage rail */}
      <div className="flex items-center" role="list" aria-label={`Pipeline stages for ${file.name}`}>
        {file.stages.map((s, i) => (
          <div key={s.name} role="listitem" className="flex items-center flex-1 last:flex-none">
            <div className="flex flex-col items-center gap-1.5 min-w-14">
              <StageDot status={s.status} />
              <span className={`text-[10px] font-mono ${s.status === 'pending' ? 'text-text-faint' : s.status === 'failed' ? 'text-red-fg' : 'text-text-muted'}`}>
                {s.name}
              </span>
              <span className="text-[9px] text-text-faint h-3">{s.ms != null ? (s.ms >= 1000 ? `${(s.ms / 1000).toFixed(1)}s` : `${s.ms}ms`) : ''}</span>
            </div>
            {i < file.stages.length - 1 && (
              <div className={`h-px flex-1 mx-1 mb-6 ${s.status === 'done' ? 'bg-sage/50' : 'bg-border'}`} />
            )}
          </div>
        ))}
      </div>

      {failed && 'error' in failed && (
        <div className="flex items-center justify-between bg-red-soft border border-red/25 rounded-lg px-3 py-2 mt-2">
          <span className="text-xs text-red-fg">{failed.error}</span>
          <Button variant="secondary" size="sm">
            <RotateCcw size={12} /> Retry stage
          </Button>
        </div>
      )}
    </Card>
  )
}

export function PipelineConsole() {
  const { sim } = useSim()

  return (
    <PageShell
      title="Upload"
      subtitle="Files move through six stages — each retryable on its own"
      actions={
        <Button variant="secondary" size="sm" kbd="⌘V">
          <ClipboardPaste size={13} /> Quick capture
        </Button>
      }
      wide
    >
      {/* dropzone */}
      <button className="w-full border border-dashed border-border-strong rounded-xl py-10 mb-6 text-sm text-text-muted hover:text-text hover:border-text-faint transition-colors flex flex-col items-center gap-2 cursor-pointer">
        <Upload size={20} strokeWidth={1.5} />
        Drop lecture files here — PDF, DOCX, PPTX · up to 20 at once
        <span className="text-[11px] text-text-faint">duplicates are detected and skipped automatically</span>
      </button>

      <SectionLabel>Processing now</SectionLabel>

      {sim === 'loading' && (
        <Card dense>
          <Skeleton className="h-4 w-56 mb-4" />
          <div className="flex gap-8">
            {Array.from({ length: 6 }).map((_, i) => (
              <Skeleton key={i} className="w-8 h-8 rounded-full" />
            ))}
          </div>
        </Card>
      )}
      {sim === 'empty' && (
        <EmptyState
          title="Nothing processing"
          hint="Drop files above — they'll appear here with live stage-by-stage progress."
        />
      )}
      {sim === 'error' && (
        <ErrorState
          title="Live progress stream disconnected"
          detail="EventSource /api/uploads/events → network error · retrying in 4s (attempt 2/5)"
          onRetry={() => {}}
        />
      )}
      {(sim === 'default' || sim === 'offline') && (
        <>
          {pipelineFiles.map((f) => (
            <FileRow key={f.name} file={f} />
          ))}
          <div className="text-[11px] text-text-faint font-mono mt-4">
            event log capped at 200 entries · full history in each file's detail view
          </div>
        </>
      )}
    </PageShell>
  )
}
