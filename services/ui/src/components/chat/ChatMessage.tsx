import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Link } from 'react-router-dom'
import type { ChatMessage as ChatMessageType } from '../../types'

interface ChatMessageProps {
  message: ChatMessageType
}

interface CitationData {
  ref?: number
  course_code?: string
  week?: number
  artifact_id?: string
  page_ref?: number
  text_snippet?: string
}

function CitationLinks({ citations }: { citations: CitationData[] }) {
  if (citations.length === 0) return null

  return (
    <div className="mt-3 pt-2 border-t border-border/50">
      <p className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-1.5">Sources</p>
      <div className="flex flex-wrap gap-1.5">
        {citations.map((c, i) => (
          <Link
            key={i}
            to={`/courses/${c.course_code}/weeks/${c.week}${c.artifact_id ? `?artifact=${c.artifact_id}` : ''}${c.page_ref ? `&page=${c.page_ref}` : ''}`}
            className="inline-flex items-center gap-1 text-xs px-2 py-1 rounded-md bg-peri-soft text-peri-fg hover:bg-peri/20 transition-colors"
            title={c.text_snippet || undefined}
          >
            <span className="font-medium">[{c.ref ?? i + 1}]</span>
            {c.course_code && <span>{c.course_code} W{c.week}</span>}
            {c.page_ref != null && <span>p.{c.page_ref}</span>}
          </Link>
        ))}
      </div>
    </div>
  )
}

export function ChatMessage({ message }: ChatMessageProps) {
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
        <CitationLinks citations={citations} />
        <p className="text-[10px] text-text-muted mt-1.5">
          {new Date(message.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
        </p>
      </div>
    </div>
  )
}
