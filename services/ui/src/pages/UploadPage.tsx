import { useRef, useState } from 'react'
import { useUpload } from '../hooks/useApi'
import { usePipelineEvents } from '../hooks/usePipelineEvents'

export function UploadPage() {
  const fileRef = useRef<HTMLInputElement>(null)
  const [artifactId, setArtifactId] = useState<string>()
  const upload = useUpload()
  const { events } = usePipelineEvents(artifactId)

  const handleUpload = async () => {
    const file = fileRef.current?.files?.[0]
    if (!file) return

    const result = await upload.mutateAsync(file)
    if (result.artifact_id !== 'pending') {
      setArtifactId(result.artifact_id)
    }
  }

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Upload Lecture</h1>

      <div className="bg-white rounded-lg shadow p-6 mb-6">
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Select a PDF, DOCX, or PPTX file
        </label>
        <div className="flex gap-4">
          <input
            ref={fileRef}
            type="file"
            accept=".pdf,.docx,.pptx"
            className="block w-full text-sm text-gray-500
              file:mr-4 file:py-2 file:px-4
              file:rounded-md file:border-0
              file:text-sm file:font-semibold
              file:bg-primary/10 file:text-primary
              hover:file:bg-primary/20"
          />
          <button
            onClick={handleUpload}
            disabled={upload.isPending}
            className="px-4 py-2 bg-primary text-white rounded-md hover:bg-primary-dark
              disabled:opacity-50 disabled:cursor-not-allowed text-sm font-medium"
          >
            {upload.isPending ? 'Uploading...' : 'Upload'}
          </button>
        </div>
        {upload.isError && (
          <p className="mt-2 text-sm text-red-500">Upload failed: {upload.error.message}</p>
        )}
        {upload.isSuccess && (
          <p className="mt-2 text-sm text-green-600">
            File uploaded. Pipeline task: {upload.data.pipeline_task_id ?? 'started'}
          </p>
        )}
      </div>

      {events.length > 0 && (
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Pipeline Progress</h2>
          <div className="space-y-2">
            {events.map((event, i) => (
              <div key={i} className="flex items-center gap-3 text-sm">
                <span
                  className={`w-2 h-2 rounded-full ${
                    event.status === 'completed'
                      ? 'bg-green-500'
                      : event.status === 'failed'
                        ? 'bg-red-500'
                        : 'bg-yellow-500'
                  }`}
                />
                <span className="font-medium text-gray-700">{event.stage}</span>
                <span className="text-gray-500">{event.status}</span>
                {event.message && <span className="text-gray-400">{event.message}</span>}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
