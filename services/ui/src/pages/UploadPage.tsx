import { useCallback, useMemo, useRef, useState } from 'react'
import { Lock, WifiOff } from 'lucide-react'
import { useAuth } from '../hooks/useAuth'
import { Card, EmptyState, PageHeader, toast } from '../components/ui'
import { DropZone } from '../components/upload/DropZone'
import { PipelineFileCard, type UploadStatus } from '../components/upload/PipelineFileCard'
import { usePipelineEvents } from '../hooks/usePipelineEvents'
import { useRetryPipeline } from '../hooks/useApi'
import { mapPipelineEventsToStages } from '../lib/pipelineStages'
import { toastMutationError } from '../lib/toast'
import { uploadApi } from '../api/endpoints'
import { useQueryClient } from '@tanstack/react-query'
import type { BatchUploadResponse } from '../types'

interface QueuedFile {
  id: string
  file: File
  status: UploadStatus
  artifactId?: string
  error?: string
}

let nextId = 0

const BATCH_THRESHOLD = 3

export function UploadPage() {
  const { isDemo } = useAuth()
  const [queue, setQueue] = useState<QueuedFile[]>([])
  const processingRef = useRef(false)
  const queryClient = useQueryClient()
  const [batchResult, setBatchResult] = useState<BatchUploadResponse | null>(null)
  const retryPipeline = useRetryPipeline()

  const artifactIds = useMemo(
    () => queue.filter((f) => f.artifactId && f.status !== 'duplicate').map((f) => f.artifactId!),
    [queue],
  )
  const { events, connectionState } = usePipelineEvents(artifactIds.length > 0 ? artifactIds : undefined)

  const processQueue = useCallback(async (updatedQueue: QueuedFile[]) => {
    if (processingRef.current) return
    processingRef.current = true

    const toProcess = updatedQueue.filter((f) => f.status === 'queued')

    // Use batch endpoint for 3+ files
    if (toProcess.length >= BATCH_THRESHOLD) {
      // Mark all as uploading
      setQueue((prev) =>
        prev.map((f) =>
          toProcess.some(tp => tp.id === f.id) ? { ...f, status: 'uploading' as const } : f
        )
      )

      try {
        const result = await uploadApi.batchUpload(toProcess.map(f => f.file))
        setBatchResult(result)

        // Update queue with results
        setQueue((prev) =>
          prev.map((f) => {
            const idx = toProcess.findIndex(tp => tp.id === f.id)
            if (idx === -1 || !result.results[idx]) return f
            const r = result.results[idx]
            if (r.status === 'processing') {
              return { ...f, status: 'done' as const, artifactId: r.artifact_id || undefined }
            }
            if (r.status === 'duplicate') {
              return { ...f, status: 'duplicate' as const, artifactId: r.artifact_id || undefined }
            }
            return { ...f, status: 'error' as const, error: r.error || 'Upload failed' }
          })
        )
      } catch (err) {
        setQueue((prev) =>
          prev.map((f) =>
            toProcess.some(tp => tp.id === f.id)
              ? { ...f, status: 'error' as const, error: err instanceof Error ? err.message : 'Batch upload failed' }
              : f
          )
        )
      }
    } else {
      // Sequential upload for small batches
      for (const item of toProcess) {
        setQueue((prev) =>
          prev.map((f) => (f.id === item.id ? { ...f, status: 'uploading' as const } : f))
        )
        try {
          const result = await uploadApi.upload(item.file)
          const status: UploadStatus = result.status === 'duplicate' ? 'duplicate' : 'done'
          setQueue((prev) =>
            prev.map((f) =>
              f.id === item.id
                ? { ...f, status, artifactId: result.artifact_id }
                : f
            )
          )
        } catch (err) {
          setQueue((prev) =>
            prev.map((f) =>
              f.id === item.id
                ? { ...f, status: 'error' as const, error: err instanceof Error ? err.message : 'Upload failed' }
                : f
            )
          )
        }
      }
    }

    processingRef.current = false
    queryClient.invalidateQueries({ queryKey: ['dashboard'] })
    queryClient.invalidateQueries({ queryKey: ['courses'] })
  }, [queryClient])

  const handleFiles = useCallback((files: File[]) => {
    setBatchResult(null)
    const newItems: QueuedFile[] = files.map((file) => ({
      id: `upload-${++nextId}`,
      file,
      status: 'queued' as const,
    }))
    setQueue((prev) => {
      const updated = [...prev, ...newItems]
      processQueue(updated)
      return updated
    })
  }, [processQueue])

  const handleRemove = useCallback((id: string) => {
    setQueue((prev) => prev.filter((f) => f.id !== id))
  }, [])

  const handleRetryStage = useCallback((artifactId: string) => {
    retryPipeline.mutate(artifactId, {
      onSuccess: (res) => toast.success(`Retrying from ${res.retrying_from_stage}`),
      onError: (err) => toastMutationError(err, () => handleRetryStage(artifactId)),
    })
  }, [retryPipeline])

  const hasActive = queue.some((f) => f.status === 'uploading')

  if (isDemo) {
    return (
      <div>
        <PageHeader
          title="Upload"
          subtitle="Files move through six stages — each retryable on its own"
        />
        <Card>
          <div className="text-center py-8">
            <Lock size={40} strokeWidth={1.25} className="mx-auto mb-4 text-text-faint" aria-hidden />
            <h3 className="text-lg font-semibold text-text mb-2">Uploads disabled in demo</h3>
            <p className="text-sm text-text-muted">
              Create a free account to upload your own lecture files and start the processing pipeline.
            </p>
          </div>
        </Card>
      </div>
    )
  }

  return (
    <div>
      <PageHeader
        title="Upload"
        subtitle="Files move through six stages — each retryable on its own"
      />

      <DropZone onFiles={handleFiles} disabled={hasActive} />

      {/* Batch result summary */}
      {batchResult && (
        <div className="bg-surface-1 rounded-xl border border-border px-4 py-3 mt-6">
          <p className="text-sm font-medium text-text">
            Batch upload: {batchResult.succeeded} succeeded, {batchResult.duplicates} duplicates, {batchResult.failed} failed
            <span className="text-text-muted"> ({batchResult.total} total)</span>
          </p>
        </div>
      )}

      <h3 className="text-[11px] font-mono uppercase tracking-wider text-text-faint mt-6 mb-3">
        Processing now
      </h3>

      {artifactIds.length > 0 && connectionState === 'reconnecting' && (
        <div className="flex items-center gap-2 bg-amber-soft border border-amber/25 rounded-lg px-3 py-2 mb-3">
          <WifiOff size={13} className="text-amber-fg shrink-0" aria-hidden />
          <span className="text-xs text-amber-fg">
            Live progress stream disconnected — reconnecting. Stages keep running on the server.
          </span>
        </div>
      )}

      {queue.length === 0 ? (
        <EmptyState
          title="Nothing processing"
          description="Drop files above — they'll appear here with live stage-by-stage progress."
        />
      ) : (
        <>
          {queue.map((f) => (
            <PipelineFileCard
              key={f.id}
              name={f.file.name}
              sizeBytes={f.file.size}
              uploadStatus={f.status}
              uploadError={f.error}
              stages={f.artifactId && f.status !== 'duplicate'
                ? mapPipelineEventsToStages(events.filter((e) => e.artifact_id === f.artifactId))
                : undefined}
              onRetryStage={f.artifactId ? () => handleRetryStage(f.artifactId!) : undefined}
              retrying={retryPipeline.isPending && retryPipeline.variables === f.artifactId}
              onRemove={f.status === 'queued' || f.status === 'error' ? () => handleRemove(f.id) : undefined}
            />
          ))}
          <p className="text-[11px] text-text-faint font-mono mt-4">
            event log capped at 200 entries · full history in each file's detail view
          </p>
        </>
      )}
    </div>
  )
}
