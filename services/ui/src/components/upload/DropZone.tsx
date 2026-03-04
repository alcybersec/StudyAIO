import { useCallback, useRef, useState } from 'react'

const ACCEPTED_EXTENSIONS = ['.pdf', '.docx', '.pptx']
const ACCEPTED_DISPLAY = 'PDF, DOCX, PPTX'

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
      <div
        onDragOver={(e) => { e.preventDefault(); if (!disabled) setDragOver(true) }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        onClick={() => !disabled && inputRef.current?.click()}
        className={`flex flex-col items-center justify-center gap-3 py-16 px-6 border-2 border-dashed rounded-xl cursor-pointer transition-all ${
          disabled
            ? 'border-border bg-surface-alt cursor-not-allowed opacity-60'
            : dragOver
              ? 'border-primary bg-primary/5 scale-[1.01]'
              : 'border-border hover:border-primary/50 hover:bg-surface-alt'
        }`}
      >
        <div className="w-14 h-14 rounded-full bg-primary/10 flex items-center justify-center text-2xl text-primary">
          {'\u2191'}
        </div>
        <div className="text-center">
          <p className="text-base font-medium text-text">
            {dragOver ? 'Drop files here' : 'Drag and drop lecture files'}
          </p>
          <p className="text-sm text-text-muted mt-1">
            or <span className="text-primary font-medium">click to browse</span>
          </p>
        </div>
        <p className="text-xs text-text-muted">Accepts {ACCEPTED_DISPLAY} — multiple files supported</p>
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPTED_EXTENSIONS.join(',')}
          multiple
          onChange={handleChange}
          className="hidden"
        />
      </div>

      <div className="flex justify-center">
        <button
          onClick={(e) => {
            e.stopPropagation()
            if (!disabled) folderInputRef.current?.click()
          }}
          disabled={disabled}
          className="inline-flex items-center gap-1.5 px-4 py-2 text-sm font-medium text-text-muted bg-surface border border-border rounded-lg hover:bg-surface-alt disabled:opacity-50 disabled:cursor-not-allowed transition-colors min-h-[44px]"
        >
          <span>{'\u{1F4C1}'}</span>
          Upload Folder
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
