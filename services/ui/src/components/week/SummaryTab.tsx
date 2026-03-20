import { useCallback } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Badge } from '../ui'
import type { SummaryData } from '../../types'

interface SummaryTabProps {
  summary: SummaryData | null
  /** Primary artifact ID — used to resolve relative image paths */
  artifactId?: string
}

export function SummaryTab({ summary, artifactId }: SummaryTabProps) {
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

  if (!summary) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-center">
        <span className="text-3xl mb-2">{'\u{1F4DD}'}</span>
        <p className="text-sm text-gray-500">No summary generated yet for this week.</p>
        <p className="text-xs text-gray-400 mt-1">Upload and process lecture files to generate a summary.</p>
      </div>
    )
  }

  return (
    <div>
      <div className="flex items-center gap-3 mb-4">
        <Badge variant="info">v{summary.version}</Badge>
        {summary.source_artifacts && (
          <span className="text-xs text-gray-400">
            From {summary.source_artifacts.length} source{summary.source_artifacts.length !== 1 ? 's' : ''}
          </span>
        )}
        <span className="text-xs text-gray-400 ml-auto">
          Updated {new Date(summary.updated_at).toLocaleDateString()}
        </span>
      </div>
      <div className="prose prose-sm max-w-none prose-headings:text-gray-900 prose-p:text-gray-700 prose-a:text-primary prose-strong:text-gray-900 prose-code:text-primary prose-code:bg-primary/5 prose-code:px-1 prose-code:py-0.5 prose-code:rounded prose-code:before:content-none prose-code:after:content-none prose-table:text-sm prose-th:bg-gray-50 prose-pre:bg-gray-900 prose-pre:text-gray-100 [&_pre_code]:text-gray-100 [&_pre_code]:bg-transparent [&_pre_code]:p-0">
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          components={{
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
    </div>
  )
}
