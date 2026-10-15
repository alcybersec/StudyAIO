import { useTranslation } from 'react-i18next'
import { Link, useLocation } from 'react-router-dom'
import { Loader2 } from 'lucide-react'
import { usePipelineProgress } from '../../contexts/pipelineProgress'

/** Compact global indicator while uploads are processing; links to Upload. */
export function PipelineActivityChip() {
  const { t } = useTranslation()
  const { activeCount } = usePipelineProgress()
  const { pathname } = useLocation()

  if (activeCount === 0 || pathname === '/upload') return null

  return (
    <Link
      to="/upload"
      role="status"
      className="fixed top-14 lg:top-2 right-3 z-40 inline-flex items-center gap-1.5 min-h-11 text-[11px] font-medium bg-peri-soft text-peri-fg rounded-full px-3 py-1 shadow-lg shadow-black/10"
    >
      <Loader2 size={11} className="animate-spin" aria-hidden />
      {t('{{count}} processing', { count: activeCount })}
    </Link>
  )
}
