import { RotateCcw, X } from 'lucide-react'
import { Badge, Button, Card } from '../ui'
import { PipelineStageRail } from './PipelineStageRail'
import type { PipelineStage } from '../../lib/pipelineStages'

export type UploadStatus = 'queued' | 'uploading' | 'duplicate' | 'done' | 'error'

interface PipelineFileCardProps {
  name: string
  sizeBytes: number
  uploadStatus: UploadStatus
  uploadError?: string
  /** Stage rail data — present once the file has an artifact in the pipeline. */
  stages?: PipelineStage[]
  onRetryStage?: () => void
  retrying?: boolean
  onRemove?: () => void
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1_048_576) return `${(bytes / 1024).toFixed(0)} KB`
  return `${(bytes / 1_048_576).toFixed(1)} MB`
}

function statusBadge(uploadStatus: UploadStatus, failedStage: PipelineStage | undefined, stages?: PipelineStage[]) {
  if (uploadStatus === 'error') return <Badge variant="danger">upload failed</Badge>
  if (uploadStatus === 'duplicate') return <Badge>duplicate · skipped</Badge>
  if (uploadStatus === 'queued') return <Badge>queued</Badge>
  if (uploadStatus === 'uploading') return <Badge variant="info">uploading</Badge>
  if (failedStage) return <Badge variant="danger">failed at {failedStage.name}</Badge>
  if (stages && stages.every((s) => s.status === 'done')) return <Badge variant="success">processed</Badge>
  return <Badge variant="info">processing</Badge>
}

export function PipelineFileCard({
  name,
  sizeBytes,
  uploadStatus,
  uploadError,
  stages,
  onRetryStage,
  retrying,
  onRemove,
}: PipelineFileCardProps) {
  const failedStage = stages?.find((s) => s.status === 'failed')

  return (
    <Card padding={false} className="p-4 mb-3">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2.5 min-w-0">
          <span className="font-mono text-[13px] font-medium text-text truncate">{name}</span>
          <span className="text-[11px] text-text-faint shrink-0">{formatSize(sizeBytes)}</span>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {statusBadge(uploadStatus, failedStage, stages)}
          {onRemove && (
            <button
              onClick={onRemove}
              className="text-text-faint hover:text-red-fg transition-colors p-1"
              aria-label={`Remove ${name}`}
            >
              <X size={13} aria-hidden />
            </button>
          )}
        </div>
      </div>

      {stages && uploadStatus !== 'duplicate' && <PipelineStageRail stages={stages} />}

      {uploadStatus === 'duplicate' && (
        <p className="text-xs text-text-faint">Already in your library — the pipeline was skipped.</p>
      )}

      {uploadStatus === 'error' && uploadError && (
        <div className="bg-red-soft border border-red/25 rounded-lg px-3 py-2 mt-2">
          <span className="text-xs text-red-fg">{uploadError}</span>
        </div>
      )}

      {failedStage && (
        <div className="flex items-center justify-between gap-3 bg-red-soft border border-red/25 rounded-lg px-3 py-2 mt-2">
          <span className="text-xs text-red-fg">{failedStage.error ?? 'Stage failed'}</span>
          {onRetryStage && (
            <Button variant="secondary" size="sm" onClick={onRetryStage} loading={retrying}>
              <RotateCcw size={12} aria-hidden /> Retry stage
            </Button>
          )}
        </div>
      )}
    </Card>
  )
}
