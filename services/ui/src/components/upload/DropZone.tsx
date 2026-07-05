import { useCallback, useRef, useState } from 'react'
import { FolderOpen, Upload } from 'lucide-react'

const ACCEPTED_EXTENSIONS = ['.pdf', '.docx', '.pptx']

interface DropZoneProps {
  onFiles: (files: File[]) => void
  disabled?: boolean
}

export function DropZone({ onFiles, disabled }: DropZoneProps) {
  const inputRef = useRef<HTMLInputElement>(null)
  const folderInputRef = useRef<HTMLInputElement>(null)
  const [dragOver, setDragOver] = useState(false)

  const filterFiles = useCallback((fileList: FileList): File[] => {
    return Array.from(fileList).filter((file) =>
      ACCEPTED_EXTENSIONS.some((ext) => file.name.toLowerCase().endsWith(ext))
    )
  }, [])

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(false)
    if (disabled) return
    const valid = filterFiles(e.dataTransfer.files)
    if (valid.length > 0) onFiles(valid)
  }, [disabled, filterFiles, onFiles])

  const handleChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files) return
    const valid = filterFiles(e.target.files)
    if (valid.length > 0) onFiles(valid)
    e.target.value = ''
  }, [filterFiles, onFiles])

  return (
    <div className="space-y-3">
      <button
        type="button"
        disabled={disabled}
        onDragOver={(e) => { e.preventDefault(); if (!disabled) setDragOver(true) }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        onClick={() => !disabled && inputRef.current?.click()}
        className={`w-full border border-dashed rounded-xl py-10 text-sm transition-colors flex flex-col items-center gap-2 ${
          disabled
            ? 'border-border text-text-faint cursor-not-allowed opacity-60'
            : dragOver
              ? 'border-sage text-text bg-sage-soft cursor-pointer'
              : 'border-border-strong text-text-muted hover:text-text hover:border-text-faint cursor-pointer'
        }`}
      >
        <Upload size={20} strokeWidth={1.5} aria-hidden />
        {dragOver ? 'Drop to upload' : 'Drop lecture files here — PDF, DOCX, PPTX · up to 20 at once'}
        <span className="text-[11px] text-text-faint">duplicates are detected and skipped automatically</span>
      </button>
      <input
        ref={inputRef}
        type="file"
        accept={ACCEPTED_EXTENSIONS.join(',')}
        multiple
        onChange={handleChange}
        className="hidden"
      />

      <div className="flex justify-center">
        <button
          type="button"
          onClick={() => !disabled && folderInputRef.current?.click()}
          disabled={disabled}
          className="inline-flex items-center gap-1.5 px-4 py-2 text-sm font-medium text-text-muted bg-surface-1 border border-border rounded-lg hover:bg-surface-2 hover:text-text disabled:opacity-50 disabled:cursor-not-allowed transition-colors min-h-[44px]"
        >
          <FolderOpen size={14} aria-hidden />
          Upload folder
        </button>
        <input
          ref={folderInputRef}
          type="file"
          // @ts-expect-error webkitdirectory is a non-standard attribute
          webkitdirectory=""
          multiple
          onChange={handleChange}
          className="hidden"
        />
      </div>
    </div>
  )
}
