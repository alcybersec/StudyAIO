import { useTranslation } from 'react-i18next'

interface CitationChipProps {
  /** 1-based source document; absent for a single-file summary. */
  doc?: number
  page: number
}

/** A small, keyboard-focusable page marker such as `p.3` or `D2 p.1`. */
export function CitationChip({ doc, page }: CitationChipProps) {
  const { t } = useTranslation()

  const label = doc != null ? `D${doc} p.${page}` : `p.${page}`
  const title =
    doc != null
      ? t('Document {{doc}}, page {{page}}', { doc, page })
      : t('Page {{page}}', { page })

  return (
    <span
      role="note"
      tabIndex={0}
      title={title}
      aria-label={title}
      className="mx-0.5 inline-flex items-center rounded bg-peri-soft px-1 align-baseline font-mono text-[10px] leading-4 text-peri-fg no-underline focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-peri"
    >
      {label}
    </span>
  )
}
