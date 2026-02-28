import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Badge } from '../ui'
import type { SummaryData } from '../../types'

interface SummaryTabProps {
  summary: SummaryData | null
}

export function SummaryTab({ summary }: SummaryTabProps) {
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
      <div className="prose prose-sm max-w-none prose-headings:text-gray-900 prose-p:text-gray-700 prose-a:text-primary prose-strong:text-gray-900 prose-code:text-primary prose-code:bg-primary/5 prose-code:px-1 prose-code:py-0.5 prose-code:rounded prose-code:before:content-none prose-code:after:content-none prose-table:text-sm prose-th:bg-gray-50">
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          components={{
            img: ({ src, alt, ...props }) => {
              const resolvedSrc = src && !src.startsWith('http') && !src.startsWith('/api/')
                ? `/api/files/${src}`
                : src
              return <img src={resolvedSrc} alt={alt ?? ''} className="rounded-lg max-w-full" {...props} />
            },
          }}
        >
          {summary.content_md}
        </ReactMarkdown>
      </div>
    </div>
  )
}
