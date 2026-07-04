import { memo, useCallback, useRef, useState } from 'react'
import { Upload } from 'lucide-react'
import { useUpload } from '../../../hooks/useApi'
import { SectionLabel } from '../../ui'

const ACCEPTED_EXT = ['.pdf', '.docx', '.pptx']

/**
 * Mutation-only widget — no query behind it, so no loading/empty/error
 * query states. Upload progress and failures render inline.
 */
export const QuickUploadWidget = memo(function QuickUploadWidget() {
  const upload = useUpload()
  const inputRef = useRef<HTMLInputElement>(null)
  const [dragOver, setDragOver] = useState(false)
  const [lastResult, setLastResult] = useState<{ ok: boolean; message: string } | null>(null)

  const handleFile = useCallback(
    async (file: File) => {
      setLastResult(null)
      try {
        const result = await upload.mutateAsync(file)
        setLastResult({ ok: true, message: `${result.filename} uploaded` })
      } catch (err) {
        setLastResult({ ok: false, message: err instanceof Error ? err.message : 'Upload failed' })
      }
    },
    [upload],
  )

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault()
      setDragOver(false)
      const file = e.dataTransfer.files[0]
      if (file) handleFile(file)
    },
    [handleFile],
  )

  const handleChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0]
      if (file) handleFile(file)
      e.target.value = ''
    },
    [handleFile],
  )

  return (
    <section className="h-full overflow-auto bg-surface-1 border border-border rounded-xl p-3">
      <SectionLabel>Quick upload</SectionLabel>
      <button
        type="button"
        onDragOver={(e) => {
          e.preventDefault()
          setDragOver(true)
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        onClick={() => inputRef.current?.click()}
        className={`w-full border border-dashed rounded-lg py-6 px-3 text-xs transition-colors flex items-center justify-center gap-2 cursor-pointer ${
          dragOver
            ? 'border-sage text-text bg-sage-soft'
            : 'border-border-strong text-text-muted hover:text-text hover:border-text-faint'
        }`}
      >
        <Upload size={14} aria-hidden />
        {upload.isPending ? 'Uploading…' : 'Drop lecture files or click — PDF, DOCX, PPTX'}
      </button>
      <input ref={inputRef} type="file" accept={ACCEPTED_EXT.join(',')} onChange={handleChange} className="hidden" />
      {lastResult && (
        <p role="status" className={`mt-2 text-xs ${lastResult.ok ? 'text-sage-fg' : 'text-red-fg'}`}>
          {lastResult.message}
        </p>
      )}
    </section>
  )
})
