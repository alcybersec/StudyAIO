import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { userErrorMessage } from '../lib/userError'
import i18n from '../i18n'
import { useTranslation } from 'react-i18next'
import { Lock, WifiOff } from 'lucide-react'
import { useAuth } from '../hooks/useAuth'
import { Card, EmptyState, PageHeader, toast } from '../components/ui'
import { DropZone } from '../components/upload/DropZone'
import { PlacementPicker } from '../components/upload/PlacementPicker'
import { AUTO_PLACEMENT, placementFromDraft, validatePlacement, type PlacementDraft } from '../lib/studyItems'
import { PipelineFileCard, type UploadStatus } from '../components/upload/PipelineFileCard'
import { usePipelineProgress } from '../contexts/pipelineProgress'
import { useRetryPipeline } from '../hooks/useApi'
import { mapPipelineEventsToStages } from '../lib/pipelineStages'
import { toastMutationError } from '../lib/toast'
import { uploadApi } from '../api/endpoints'
import { useQueryClient } from '@tanstack/react-query'
import type { BatchUploadResponse, UploadPlacement } from '../types'

interface QueuedFile {
  id: string
  file: File
  status: UploadStatus
  artifactId?: string
  error?: string
  /** Explicit course + week chosen when the file was added; absent = AI classifies. */
  placement?: UploadPlacement
}

let nextId = 0

const BATCH_THRESHOLD = 3

export function UploadPage() {
  const { t } = useTranslation()

  const { isDemo } = useAuth()
  const [queue, setQueue] = useState<QueuedFile[]>([])
  const processingRef = useRef(false)
  const queryClient = useQueryClient()
  const [batchResult, setBatchResult] = useState<BatchUploadResponse | null>(null)
  const retryPipeline = useRetryPipeline()
  const [placementDraft, setPlacementDraft] = useState<PlacementDraft>(AUTO_PLACEMENT)
  const placementErrors = validatePlacement(placementDraft)
  const placementValid = Object.keys(placementErrors).length === 0

  const artifactIds = useMemo(
    () => queue.filter((f) => f.artifactId && f.status !== 'duplicate').map((f) => f.artifactId!),
    [queue],
  )
  const { events, connectionState, uploads, track } = usePipelineProgress()

  // Hand uploaded artifacts to the app-level provider so they stay visible
  // after the user navigates away and back.
  useEffect(() => {
    for (const f of queue) {
      if (f.artifactId && f.status !== 'duplicate') {
        track({ key: f.id, name: f.file.name, sizeBytes: f.file.size, artifactId: f.artifactId, placed: !!f.placement })
      }
    }
  }, [queue, track])

  const restored = useMemo(
    () => uploads.filter((u) => !queue.some((f) => f.id === u.key)),
    [uploads, queue],
  )

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
        const result = await uploadApi.batchUpload(toProcess.map(f => f.file), toProcess[0].placement)
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
            return { ...f, status: 'error' as const, error: i18n.t('Upload failed') }
          })
        )
      } catch (err) {
        setQueue((prev) =>
          prev.map((f) =>
            toProcess.some(tp => tp.id === f.id)
              ? { ...f, status: 'error' as const, error: userErrorMessage(err, i18n.t('Upload failed')) }
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
          const result = await uploadApi.upload(item.file, item.placement)
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
                ? { ...f, status: 'error' as const, error: userErrorMessage(err, i18n.t('Upload failed')) }
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
    if (!placementValid) return
    const placement = placementFromDraft(placementDraft)
    setBatchResult(null)
    const newItems: QueuedFile[] = files.map((file) => ({
      id: `upload-${++nextId}`,
      file,
      status: 'queued' as const,
      placement,
    }))
    setQueue((prev) => {
      const updated = [...prev, ...newItems]
      processQueue(updated)
      return updated
    })
  }, [processQueue, placementValid, placementDraft])

  const handleRemove = useCallback((id: string) => {
    setQueue((prev) => prev.filter((f) => f.id !== id))
  }, [])

  const handleRetryStage = useCallback((artifactId: string) => {
    retryPipeline.mutate(artifactId, {
      onSuccess: (res) => toast.success(i18n.t('Retrying from {{stage}}', { stage: res.retrying_from_stage })),
      onError: (err) => toastMutationError(err, () => handleRetryStage(artifactId)),
    })
  }, [retryPipeline])

  const hasActive = queue.some((f) => f.status === 'uploading')

  if (isDemo) {
    return (
      <div>
        <PageHeader
          title={t('Upload')}
          subtitle={t('Files move through six stages — each retryable on its own')}
        />
        <Card>
          <div className="text-center py-8">
            <Lock size={40} strokeWidth={1.25} className="mx-auto mb-4 text-text-faint" aria-hidden />
            <h3 className="text-lg font-semibold text-text mb-2">{t('Uploads disabled in demo')}</h3>
            <p className="text-sm text-text-muted">
              {t('Create a free account to upload your own lecture files and start the processing pipeline.')}
            </p>
          </div>
        </Card>
      </div>
    )
  }

  return (
    <div>
      <PageHeader
        title={t('Upload')}
        subtitle={t('Files move through six stages — each retryable on its own')}
      />

      <PlacementPicker
        value={placementDraft}
        onChange={setPlacementDraft}
        errors={placementErrors}
        disabled={hasActive}
      />

      <DropZone onFiles={handleFiles} disabled={hasActive || !placementValid} />

      {/* Batch result summary */}
      {batchResult && (
        <div className="bg-surface-1 rounded-xl border border-border px-4 py-3 mt-6">
          <p className="text-sm font-medium text-text">
            {t('Batch upload: {{succeeded}} succeeded, {{duplicates}} duplicates, {{failed}} failed', {
              succeeded: batchResult.succeeded,
              duplicates: batchResult.duplicates,
              failed: batchResult.failed,
            })}
            <span className="text-text-muted"> {t('({{count}} total)', { count: batchResult.total })}</span>
          </p>
        </div>
      )}

      <h3 className="text-[11px] font-mono uppercase tracking-wider text-text-faint mt-6 mb-3">
        {t('Processing now')}
      </h3>

      {artifactIds.length > 0 && connectionState === 'reconnecting' && (
        <div className="flex items-center gap-2 bg-amber-soft border border-amber/25 rounded-lg px-3 py-2 mb-3">
          <WifiOff size={13} className="text-amber-fg shrink-0" aria-hidden />
          <span className="text-xs text-amber-fg">
            {t('Live progress stream disconnected — reconnecting. Stages keep running on the server.')}
          </span>
        </div>
      )}

      {queue.length === 0 && restored.length === 0 ? (
        <EmptyState
          title={t('Nothing processing')}
          description={t("Drop files above — they'll appear here with live stage-by-stage progress.")}
        />
      ) : (
        <>
          {restored.map((u) => (
            <PipelineFileCard
              key={u.key}
              name={u.name}
              sizeBytes={u.sizeBytes}
              uploadStatus="done"
              stages={mapPipelineEventsToStages(events.filter((e) => e.artifact_id === u.artifactId), { placed: u.placed })}
              onRetryStage={() => handleRetryStage(u.artifactId)}
              retrying={retryPipeline.isPending && retryPipeline.variables === u.artifactId}
            />
          ))}
          {queue.map((f) => (
            <PipelineFileCard
              key={f.id}
              name={f.file.name}
              sizeBytes={f.file.size}
              uploadStatus={f.status}
              uploadError={f.error}
              stages={f.artifactId && f.status !== 'duplicate'
                ? mapPipelineEventsToStages(events.filter((e) => e.artifact_id === f.artifactId), { placed: !!f.placement })
                : undefined}
              onRetryStage={f.artifactId ? () => handleRetryStage(f.artifactId!) : undefined}
              retrying={retryPipeline.isPending && retryPipeline.variables === f.artifactId}
              onRemove={f.status === 'queued' || f.status === 'error' ? () => handleRemove(f.id) : undefined}
            />
          ))}
          <p className="text-[11px] text-text-faint font-mono mt-4">
            {t("event log capped at 200 entries · full history in each file's detail view")}
          </p>
        </>
      )}
    </div>
  )
}
