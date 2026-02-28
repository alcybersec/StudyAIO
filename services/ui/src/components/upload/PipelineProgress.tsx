import type { PipelineEvent } from '../../types'

const STAGES = ['ingest', 'classify', 'extract', 'summarize']

interface PipelineProgressProps {
  events: PipelineEvent[]
  artifactId: string
}

export function PipelineProgress({ events, artifactId }: PipelineProgressProps) {
  const myEvents = events.filter((e) => e.artifact_id === artifactId)
  if (myEvents.length === 0) return null

  const stageStatus = new Map<string, string>()
  for (const e of myEvents) {
    stageStatus.set(e.stage, e.status)
  }

  return (
    <div className="flex items-center gap-1 mt-2">
      {STAGES.map((stage, i) => {
        const status = stageStatus.get(stage)
        const isCompleted = status === 'completed'
        const isFailed = status === 'failed'
        const isRunning = status === 'running' || status === 'started'

        return (
          <div key={stage} className="flex items-center gap-1">
            <div
              className={`flex items-center gap-1.5 px-2 py-1 rounded text-xs font-medium ${
                isCompleted
                  ? 'bg-emerald-50 text-emerald-700'
                  : isFailed
                    ? 'bg-red-50 text-red-700'
                    : isRunning
                      ? 'bg-amber-50 text-amber-700'
                      : 'bg-gray-50 text-gray-400'
              }`}
              title={status ?? 'pending'}
            >
              <span>
                {isCompleted ? '\u2713' : isFailed ? '\u2717' : isRunning ? '\u25CB' : '\u2022'}
              </span>
              <span className="hidden sm:inline">{stage}</span>
            </div>
            {i < STAGES.length - 1 && (
              <span className={`text-xs ${isCompleted ? 'text-emerald-300' : 'text-gray-200'}`}>{'\u2192'}</span>
            )}
          </div>
        )
      })}
    </div>
  )
}
