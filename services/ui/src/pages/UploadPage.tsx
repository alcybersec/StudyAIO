import { useCallback, useMemo, useRef, useState } from 'react'
import { PageHeader } from '../components/ui'
import { DropZone } from '../components/upload/DropZone'
import { FileQueue, type QueuedFile } from '../components/upload/FileQueue'
import { PipelineProgress } from '../components/upload/PipelineProgress'
import { usePipelineEvents } from '../hooks/usePipelineEvents'
import { uploadApi } from '../api/endpoints'
import { useQueryClient } from '@tanstack/react-query'

let nextId = 0

export function UploadPage() {
  const [queue, setQueue] = useState<QueuedFile[]>([])
  const processingRef = useRef(false)
  const queryClient = useQueryClient()

  const artifactIds = useMemo(
    () => queue.filter((f) => f.artifactId).map((f) => f.artifactId!),
    [queue],
  )
  const { events } = usePipelineEvents(artifactIds.length > 0 ? artifactIds : undefined)

  const processQueue = useCallback(async (updatedQueue: QueuedFile[]) => {
    if (processingRef.current) return
    processingRef.current = true

    const toProcess = updatedQueue.filter((f) => f.status === 'queued')
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

    processingRef.current = false
    queryClient.invalidateQueries({ queryKey: ['dashboard'] })
    queryClient.invalidateQueries({ queryKey: ['courses'] })
  }, [queryClient])

  const handleFiles = useCallback((files: File[]) => {
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

  return (
    <div>
      <PageHeader
        title="Upload Lectures"
        subtitle="Upload PDF, DOCX, or PPTX files to start the processing pipeline"
      />

      <div className="space-y-6">
        <DropZone onFiles={handleFiles} disabled={hasActive} />

        <FileQueue files={queue} onRemove={handleRemove} />

        {/* Pipeline progress per uploaded artifact */}
        {queue.filter((f) => f.artifactId).map((f) => (
          <div key={f.id} className="bg-white rounded-xl border border-gray-200 px-4 py-3">
            <p className="text-sm font-medium text-gray-900 truncate">{f.file.name}</p>
            <PipelineProgress events={events} artifactId={f.artifactId!} />
          </div>
        ))}
      </div>
    </div>
  )
}
