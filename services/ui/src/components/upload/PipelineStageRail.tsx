import { Check, Clock, Loader2, X } from 'lucide-react'
import { formatStageMs, type PipelineStage, type StageStatus } from '../../lib/pipelineStages'

function StageDot({ status }: { status: StageStatus }) {
  if (status === 'done') {
    return (
      <span className="w-5 h-5 rounded-full bg-sage-soft text-sage-fg flex items-center justify-center shrink-0">
        <Check size={11} strokeWidth={3} aria-hidden />
      </span>
    )
  }
  if (status === 'running') {
    return (
      <span className="w-5 h-5 rounded-full bg-peri-soft text-peri-fg flex items-center justify-center shrink-0">
        <Loader2 size={11} className="animate-spin" aria-hidden />
      </span>
    )
  }
  if (status === 'failed') {
    return (
      <span className="w-5 h-5 rounded-full bg-red-soft text-red-fg flex items-center justify-center shrink-0">
        <X size={11} strokeWidth={3} aria-hidden />
      </span>
    )
  }
  return (
    <span className="w-5 h-5 rounded-full bg-surface-2 text-text-faint flex items-center justify-center shrink-0">
      <Clock size={10} aria-hidden />
    </span>
  )
}

const labelClass: Record<StageStatus, string> = {
  pending: 'text-text-faint',
  running: 'text-text-muted',
  done: 'text-text-muted',
  failed: 'text-red-fg',
}

interface PipelineStageRailProps {
  stages: PipelineStage[]
}

/** Pure six-stage rail: dots, per-stage timing and connector lines. */
export function PipelineStageRail({ stages }: PipelineStageRailProps) {
  return (
    <div className="flex items-center" role="list" aria-label="Pipeline stages">
      {stages.map((stage, i) => (
        <div
          key={stage.name}
          role="listitem"
          aria-label={`${stage.name}: ${stage.status}`}
          className="flex items-center flex-1 last:flex-none"
        >
          <div className="flex flex-col items-center gap-1.5 min-w-14">
            <StageDot status={stage.status} />
            <span className={`text-[10px] font-mono ${labelClass[stage.status]}`}>{stage.name}</span>
            <span className="text-[9px] text-text-faint h-3">
              {stage.ms != null ? formatStageMs(stage.ms) : ''}
            </span>
          </div>
          {i < stages.length - 1 && (
            <div
              className={`h-px flex-1 mx-1 mb-6 ${stage.status === 'done' ? 'bg-sage/50' : 'bg-border'}`}
              aria-hidden
            />
          )}
        </div>
      ))}
    </div>
  )
}
