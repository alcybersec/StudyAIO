import { exportApi } from '../../api/endpoints'

interface ExportButtonProps {
  courseCode: string
  weeks?: number[]
  label?: string
  className?: string
}

export function ExportButton({ courseCode, weeks, label = 'Export to Obsidian', className }: ExportButtonProps) {
  const handleExport = () => {
    const url = exportApi.obsidianVaultUrl(courseCode, weeks)
    window.open(url, '_blank')
  }

  return (
    <button
      onClick={handleExport}
      className={className || 'inline-flex items-center gap-1.5 px-3 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors min-h-[44px]'}
      title={`Export ${courseCode} as Obsidian vault`}
    >
      <span className="text-base">{'\u{1F4E6}'}</span>
      {label}
    </button>
  )
}
