import { useEffect, useRef } from 'react'
import { WifiOff } from 'lucide-react'
import { useChatMessages } from '../../hooks/useApi'
import { useStreamingChat } from '../../hooks/useStreamingChat'
import { ChatMessage } from './ChatMessage'
import { ChatInput } from './ChatInput'
import { StreamingMessage } from './StreamingMessage'

interface ChatWindowProps {
  sessionId: string
}

export function ChatWindow({ sessionId }: ChatWindowProps) {
  const { data: messagesData, isLoading } = useChatMessages(sessionId)
  const messages = messagesData?.messages ?? []
  const { isStreaming, streamingText, error, connectionState, retryAttempt, sendStreaming, resume } =
    useStreamingChat(sessionId)
  const bottomRef = useRef<HTMLDivElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)

  // Auto-scroll to bottom on new messages or streaming text
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages.length, isStreaming, streamingText])

  const handleSend = (content: string) => {
    sendStreaming(content)
  }

  return (
    <div className="flex flex-col h-full">
      {/* Messages area */}
      <div ref={containerRef} className="flex-1 overflow-y-auto px-3 sm:px-6 py-4">
        {isLoading ? (
          <div className="flex items-center justify-center h-full">
            <div className="animate-spin w-6 h-6 border-2 border-primary border-t-transparent rounded-full" />
          </div>
        ) : messages.length === 0 && !isStreaming ? (
          <div className="flex flex-col items-center justify-center h-full text-text-muted">
            <svg className="w-12 h-12 mb-3 opacity-40" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M7.5 8.25h9m-9 3H12m-9.75 1.51c0 1.6 1.123 2.994 2.707 3.227 1.129.166 2.27.293 3.423.379.35.026.67.21.865.501L12 21l2.755-4.133a1.14 1.14 0 01.865-.501 48.172 48.172 0 003.423-.379c1.584-.233 2.707-1.626 2.707-3.228V6.741c0-1.602-1.123-2.995-2.707-3.228A48.394 48.394 0 0012 3c-2.392 0-4.744.175-7.043.513C3.373 3.746 2.25 5.14 2.25 6.741v6.018z" />
            </svg>
            <p className="text-sm font-medium">Start the conversation</p>
            <p className="text-xs mt-1">Ask about your study materials, get explanations, or quiz yourself</p>
          </div>
        ) : (
          <div className="space-y-4 max-w-3xl mx-auto">
            {messages.map((msg) => (
              <ChatMessage key={msg.id} message={msg} />
            ))}
            {isStreaming && streamingText && (
              <StreamingMessage text={streamingText} />
            )}
            <div ref={bottomRef} />
          </div>
        )}
      </div>

      {/* Interrupted stream — auto-retrying */}
      {connectionState === 'interrupted' && (
        <div
          role="alert"
          className="mx-3 sm:mx-6 mb-2 flex items-center gap-2.5 border border-amber/25 bg-amber-soft rounded-lg px-3.5 py-2.5 text-xs text-amber-fg"
        >
          <WifiOff size={13} aria-hidden />
          Stream interrupted — reconnecting (attempt {retryAttempt})…
        </div>
      )}

      {/* Error display — retries exhausted or request rejected */}
      {connectionState === 'error' && error && (
        <div
          role="alert"
          className="mx-3 sm:mx-6 mb-2 flex items-center gap-2.5 border border-red/25 bg-red-soft rounded-lg px-3.5 py-2.5 text-xs text-red-fg"
        >
          <WifiOff size={13} aria-hidden />
          <span className="flex-1">Connection lost: {error}</span>
          <button
            onClick={() => resume()}
            className="shrink-0 px-2.5 py-1 rounded-md border border-red/30 font-medium hover:bg-red/15 transition-colors"
          >
            Resume now
          </button>
        </div>
      )}

      {/* Input */}
      <ChatInput onSend={handleSend} disabled={isStreaming} />
    </div>
  )
}
