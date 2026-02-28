import { useCallback, useRef, useState } from 'react'

const ACCEPTED_EXTENSIONS = ['.pdf', '.docx', '.pptx']
const ACCEPTED_DISPLAY = 'PDF, DOCX, PPTX'

interface DropZoneProps {
  onFiles: (files: File[]) => void
  disabled?: boolean
}

export function DropZone({ onFiles, disabled }: DropZoneProps) {
  const inputRef = useRef<HTMLInputElement>(null)
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
    <div
      onDragOver={(e) => { e.preventDefault(); if (!disabled) setDragOver(true) }}
      onDragLeave={() => setDragOver(false)}
      onDrop={handleDrop}
      onClick={() => !disabled && inputRef.current?.click()}
      className={`flex flex-col items-center justify-center gap-3 py-16 px-6 border-2 border-dashed rounded-xl cursor-pointer transition-all ${
        disabled
          ? 'border-gray-200 bg-gray-50 cursor-not-allowed opacity-60'
          : dragOver
            ? 'border-primary bg-primary/5 scale-[1.01]'
            : 'border-gray-300 hover:border-primary/50 hover:bg-gray-50'
      }`}
    >
      <div className="w-14 h-14 rounded-full bg-primary/10 flex items-center justify-center text-2xl text-primary">
        {'\u2191'}
      </div>
      <div className="text-center">
        <p className="text-base font-medium text-gray-700">
          {dragOver ? 'Drop files here' : 'Drag and drop lecture files'}
        </p>
        <p className="text-sm text-gray-500 mt-1">
          or <span className="text-primary font-medium">click to browse</span>
        </p>
      </div>
      <p className="text-xs text-gray-400">Accepts {ACCEPTED_DISPLAY} — multiple files supported</p>
      <input
        ref={inputRef}
        type="file"
        accept={ACCEPTED_EXTENSIONS.join(',')}
        multiple
        onChange={handleChange}
        className="hidden"
      />
    </div>
  )
}
