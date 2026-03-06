import { useCallback, useMemo, useRef, useState } from 'react'
import { useAuth } from '../hooks/useAuth'
import { Card, PageHeader, ConnectionBanner } from '../components/ui'
import { DropZone } from '../components/upload/DropZone'
import { FileQueue, type QueuedFile } from '../components/upload/FileQueue'
import { PipelineProgress } from '../components/upload/PipelineProgress'
import { usePipelineEvents } from '../hooks/usePipelineEvents'
import { uploadApi } from '../api/endpoints'
import { useQueryClient } from '@tanstack/react-query'
import type { BatchUploadResponse } from '../types'

let nextId = 0

const BATCH_THRESHOLD = 3

export function UploadPage() {
  const { isDemo } = useAuth()
  const [queue, setQueue] = useState<QueuedFile[]>([])
  const processingRef = useRef(false)
  const queryClient = useQueryClient()
  const [batchResult, setBatchResult] = useState<BatchUploadResponse | null>(null)

  const artifactIds = useMemo(
    () => queue.filter((f) => f.artifactId).map((f) => f.artifactId!),
    [queue],
  )
  const { events, connected } = usePipelineEvents(artifactIds.length > 0 ? artifactIds : undefined)

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
              return { ...f, status: 'done' as const, artifactId: r.artifact_id || undefined }
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
          setQueue((prev) =>
            prev.map((f) =>
              f.id === item.id
                ? { ...f, status: 'done' as const, artifactId: result.artifact_id }
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

  const hasActive = queue.some((f) => f.status === 'uploading')

  if (isDemo) {
    return (
      <div>
        <PageHeader
          title="Upload Lectures"
          subtitle="Upload PDF, DOCX, or PPTX files to start the processing pipeline"
        />
        <Card>
          <div className="text-center py-8">
            <svg className="w-12 h-12 mx-auto mb-4 text-text-muted" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
            </svg>
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
        title="Upload Lectures"
        subtitle="Upload PDF, DOCX, or PPTX files to start the processing pipeline"
      />

      <div className="space-y-6">
        <ConnectionBanner connected={connected} />
        <DropZone onFiles={handleFiles} disabled={hasActive} />

        {/* Batch result summary */}
        {batchResult && (
          <div className="bg-surface rounded-xl border border-border px-4 py-3">
            <p className="text-sm font-medium text-text">
              Batch upload: {batchResult.succeeded} succeeded, {batchResult.duplicates} duplicates, {batchResult.failed} failed
              <span className="text-text-muted"> ({batchResult.total} total)</span>
            </p>
          </div>
        )}

        <FileQueue files={queue} onRemove={handleRemove} />

        {/* Pipeline progress per uploaded artifact */}
        {queue.filter((f) => f.artifactId).map((f) => (
          <div key={f.id} className="bg-surface rounded-xl border border-border px-4 py-3">
            <p className="text-sm font-medium text-text truncate">{f.file.name}</p>
            <PipelineProgress events={events} artifactId={f.artifactId!} />
          </div>
        ))}
      </div>
    </div>
  )
}
