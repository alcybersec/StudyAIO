import { useCallback, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Badge } from '../ui'
import { AiFeedbackControl } from '../ui/AiFeedbackControl'
import { CitationChip } from './CitationChip'
import { recordUsageEvent } from '../../api/usage'
import { remarkCitations } from '../../lib/citations'
import type { SummaryData } from '../../types'

interface SummaryTabProps {
  summary: SummaryData | null
  /** Primary artifact ID — used to resolve relative image paths */
  artifactId?: string
}

export function SummaryTab({ summary, artifactId }: SummaryTabProps) {
  const { t } = useTranslation()

  const sourceArtifacts = summary?.source_artifacts ?? []

  const handleImgError = useCallback(
    (e: React.SyntheticEvent<HTMLImageElement>) => {
      const img = e.currentTarget
      const triedIdx = parseInt(img.dataset.aidIdx ?? '0', 10)
      const filename = img.dataset.filename ?? ''
      const nextIdx = triedIdx + 1
      if (nextIdx < sourceArtifacts.length && filename) {
        img.dataset.aidIdx = String(nextIdx)
        img.src = `/api/files/extractions/${sourceArtifacts[nextIdx]}/images/${filename}`
      } else {
        // All artifacts tried — hide broken image
        img.style.display = 'none'
      }
    },
    [sourceArtifacts],
  )

  // One view event per summary shown. Fire-and-forget: it never blocks the page.
  const summaryId = summary?.id
  const courseId = summary?.course_id
  useEffect(() => {
    if (summaryId) recordUsageEvent('summary_viewed', courseId)
  }, [summaryId, courseId])

  if (!summary) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-center">
        <span className="text-3xl mb-2">{'\u{1F4DD}'}</span>
        <p className="text-sm text-text-muted">{t('No summary generated yet for this week.')}</p>
        <p className="text-xs text-text-faint mt-1">{t('Upload and process lecture files to generate a summary.')}</p>
      </div>
    )
  }

  return (
    <div>
      <div className="flex items-center gap-3 mb-4">
        <Badge variant="info">v{summary.version}</Badge>
        {summary.source_artifacts && (
          <span className="text-xs text-text-faint">
            {t('From {{count}} source', { count: summary.source_artifacts.length })}
          </span>
        )}
        <span className="text-xs text-text-faint ml-auto">
          {t('Updated {{date}}', { date: new Date(summary.updated_at).toLocaleDateString() })}
        </span>
      </div>
      <div className="prose prose-sm max-w-none prose-headings:text-text prose-p:text-text prose-li:text-text prose-td:text-text prose-a:text-peri-fg prose-strong:text-text prose-code:text-peri-fg prose-code:bg-peri/5 prose-code:px-1 prose-code:py-0.5 prose-code:rounded prose-code:before:content-none prose-code:after:content-none prose-table:text-sm prose-th:bg-surface-2 prose-th:text-text prose-pre:bg-surface-2 prose-pre:text-text [&_pre_code]:text-text [&_pre_code]:bg-transparent [&_pre_code]:p-0">
        <ReactMarkdown
          remarkPlugins={[remarkGfm, remarkCitations]}
          components={{
            span: ({ node, ...rest }) => {
              void node // react-markdown's AST node; must not reach the DOM
              const attrs = rest as Record<string, string | undefined>
              const page = attrs['data-cite-page']
              if (page === undefined) return <span {...rest} />
              const doc = attrs['data-cite-doc']
              return <CitationChip page={Number(page)} doc={doc ? Number(doc) : undefined} />
            },
            img: ({ src, alt, ...props }) => {
              let resolvedSrc = src
              const filename = src ?? ''
              if (src && !src.startsWith('http') && !src.startsWith('/api/')) {
                const aid = artifactId ?? sourceArtifacts[0]
                resolvedSrc = aid
                  ? `/api/files/extractions/${aid}/images/${src}`
                  : `/api/files/${src}`
              }
              return (
                <img
                  src={resolvedSrc}
                  alt={alt ?? ''}
                  className="rounded-lg max-w-full"
                  data-filename={filename}
                  data-aid-idx="0"
                  onError={handleImgError}
                  {...props}
                />
              )
            },
          }}
        >
          {summary.content_md}
        </ReactMarkdown>
      </div>
      <div className="mt-4 pt-3 border-t border-border/50">
        <AiFeedbackControl targetType="summary" targetId={summary.id} />
      </div>
    </div>
  )
}
