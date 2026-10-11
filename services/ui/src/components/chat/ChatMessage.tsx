import ReactMarkdown from 'react-markdown'
import { useTranslation } from 'react-i18next'
import remarkGfm from 'remark-gfm'
import { Link } from 'react-router-dom'
import type { ChatMessage as ChatMessageType } from '../../types'
import { ChatActionButton } from './ChatActionButton'
import { AiFeedbackControl } from '../ui/AiFeedbackControl'

interface ChatMessageProps {
  message: ChatMessageType
  /** Ids of every assistant message on screen, so their votes load in one request. */
  feedbackBatchIds?: string[]
}

interface CitationData {
  ref?: number
  course_code?: string | null
  week?: number | null
  artifact_id?: string | null
  page_ref?: number | null
  text_snippet?: string
}

function citationHref(c: CitationData): string {
  if (!c.course_code) return '/courses'
  const base =
    c.week != null ? `/courses/${c.course_code}/weeks/${c.week}` : `/courses/${c.course_code}`
  const params = new URLSearchParams()
  if (c.artifact_id) params.set('artifact', c.artifact_id)
  if (c.artifact_id && c.page_ref) params.set('page', String(c.page_ref))
  const qs = params.toString()
  return qs ? `${base}?${qs}` : base
}

function CitationLinks({ citations }: { citations: CitationData[] }) {
  const { t } = useTranslation()

  if (citations.length === 0) return null

  return (
    <div className="mt-3 pt-2 border-t border-border/50">
      <p className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-1.5">{t('Sources')}</p>
      <div className="flex flex-wrap gap-1.5">
        {citations.map((c, i) => (
          <Link
            key={i}
            to={citationHref(c)}
            className="inline-flex items-center gap-1 text-xs px-2 py-1 rounded-md bg-peri-soft text-peri-fg hover:bg-peri/20 transition-colors"
            title={c.text_snippet || undefined}
          >
            <span className="font-medium">[{c.ref ?? i + 1}]</span>
            {c.course_code && (
              <span>
                {c.course_code}
                {c.week != null && ` W${c.week}`}
              </span>
            )}
            {c.page_ref != null && <span>p.{c.page_ref}</span>}
          </Link>
        ))}
      </div>
    </div>
  )
}

export function ChatMessage({ message, feedbackBatchIds }: ChatMessageProps) {
  const isUser = message.role === 'user'
  const citations = (message.citations_json as CitationData[] | null) ?? []

  if (isUser) {
    return (
      <div className="flex justify-end">
        <div className="max-w-[80%] sm:max-w-[70%] rounded-2xl rounded-br-md px-4 py-2.5 bg-peri-soft text-text">
          <p className="text-sm whitespace-pre-wrap break-words">{message.content}</p>
          <p className="text-[10px] text-text-muted mt-1 text-right">
            {new Date(message.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="flex justify-start">
      <div className="max-w-[85%] sm:max-w-[75%] rounded-2xl rounded-bl-md px-4 py-2.5 bg-surface-0 text-text">
        <div className="prose prose-sm dark:prose-invert max-w-none text-text [&_p]:mb-2 [&_p:last-child]:mb-0 [&_pre]:bg-black/5 [&_pre]:dark:bg-white/5 [&_code]:text-xs [&_table]:text-xs [&_li]:my-0.5">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>
            {message.content}
          </ReactMarkdown>
        </div>
        {message.action && <ChatActionButton action={message.action} />}
        <CitationLinks citations={citations} />
        <AiFeedbackControl
          targetType="answer"
          targetId={message.id}
          batchIds={feedbackBatchIds}
          className="mt-2"
        />
        <p className="text-[10px] text-text-muted mt-1.5">
          {new Date(message.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
        </p>
      </div>
    </div>
  )
}
