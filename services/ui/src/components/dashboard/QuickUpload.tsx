import { useCallback, useRef, useState } from 'react'
import { useUpload } from '../../hooks/useApi'
import { Card } from '../ui'

const ACCEPTED_EXT = ['.pdf', '.docx', '.pptx']

export function QuickUpload() {
  const upload = useUpload()
  const inputRef = useRef<HTMLInputElement>(null)
  const [dragOver, setDragOver] = useState(false)
  const [lastResult, setLastResult] = useState<{ ok: boolean; message: string } | null>(null)

  const handleFile = useCallback(async (file: File) => {
    setLastResult(null)
    try {
      const result = await upload.mutateAsync(file)
      setLastResult({ ok: true, message: `${result.filename} uploaded successfully` })
    } catch (err) {
      setLastResult({ ok: false, message: err instanceof Error ? err.message : 'Upload failed' })
    }
  }, [upload])

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(false)
    const file = e.dataTransfer.files[0]
    if (file) handleFile(file)
  }, [handleFile])

  const handleChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) handleFile(file)
    e.target.value = ''
  }, [handleFile])

  return (
    <Card>
      <h2 className="text-sm font-semibold text-gray-900 mb-3">Quick Upload</h2>
      <div
        onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        onClick={() => inputRef.current?.click()}
        className={`flex flex-col items-center justify-center gap-2 py-6 px-4 border-2 border-dashed rounded-lg cursor-pointer transition-colors ${
          dragOver
            ? 'border-primary bg-primary/5'
            : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'
        }`}
      >
        <span className="text-2xl text-gray-400">{'\u2191'}</span>
        <p className="text-sm text-gray-500">
          {upload.isPending ? 'Uploading...' : 'Drop a file or click to browse'}
        </p>
        <p className="text-xs text-gray-400">PDF, DOCX, or PPTX</p>
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPTED_EXT.join(',')}
          onChange={handleChange}
          className="hidden"
        />
      </div>
      {lastResult && (
        <p className={`mt-2 text-sm ${lastResult.ok ? 'text-emerald-600' : 'text-red-500'}`}>
          {lastResult.message}
        </p>
      )}
    </Card>
  )
}
