import { useEffect, useMemo, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { MessagesSquare, PanelRightOpen } from 'lucide-react'
import { AskComposer, type AskScope } from '../components/ask/AskComposer'
import { SessionRail } from '../components/ask/SessionRail'
import { ChatMessage } from '../components/chat/ChatMessage'
import { StreamingMessage } from '../components/chat/StreamingMessage'
import { Button } from '../components/ui/Button'
import { EmptyState } from '../components/ui/EmptyState'
import { ErrorBanner } from '../components/ui/ErrorBanner'
import { Sheet } from '../components/ui/Sheet'
import { useChatMessages, useChatSessions, useCreateChatSession } from '../hooks/useApi'
import { useStreamingChat } from '../hooks/useStreamingChat'

export function AskPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const selectedSessionId = searchParams.get('session') || ''
  const [mobileSessionsOpen, setMobileSessionsOpen] = useState(false)
  // Scope chips prefill from ?course=&week= (WeekView "ask about this week")
  const [scope, setScope] = useState<AskScope>(() => {
    const week = Number(searchParams.get('week'))
    return {
      courseCode: searchParams.get('course'),
      week: Number.isInteger(week) && week > 0 ? week : null,
    }
  })

  const { data: sessionsData, error: sessionsError, refetch: refetchSessions } = useChatSessions()
  const sessions = useMemo(() => sessionsData?.sessions ?? [], [sessionsData])
  const createSession = useCreateChatSession()

  const handleSelectSession = (id: string) => {
    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev)
        next.set('session', id)
        return next
      },
      { replace: true },
    )
    setMobileSessionsOpen(false)
  }

  const handleNewQuestion = () => {
    createSession.mutate(
      {},
      {
        onSuccess: (session) => handleSelectSession(session.id),
      },
    )
  }

  // Auto-select the most recent session when none is selected
  useEffect(() => {
    if (!selectedSessionId && sessions.length > 0) {
      handleSelectSession(sessions[0].id)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessions, selectedSessionId])

  return (
    <div className="flex flex-col flex-1 min-h-0">
      {sessionsError && (
        <div className="px-4 pt-2">
          <ErrorBanner message="Failed to load your sessions." onRetry={() => refetchSessions()} />
        </div>
      )}

      {/* Mobile header with sessions toggle */}
      <div className="lg:hidden flex items-center justify-between px-4 py-2 border-b border-border bg-surface-1">
        <h1 className="text-lg font-semibold text-text">Ask</h1>
        <button
          type="button"
          onClick={() => setMobileSessionsOpen(true)}
          aria-label="Open sessions list"
          className="p-2 rounded-lg text-text-muted hover:text-text hover:bg-surface-2 transition-colors min-h-[44px] min-w-[44px] flex items-center justify-center cursor-pointer"
        >
          <PanelRightOpen size={18} aria-hidden />
        </button>
      </div>

      <div className="flex flex-1 overflow-hidden">
        {/* Desktop session rail */}
        <aside className="hidden lg:flex flex-col w-60 shrink-0 border-r border-border">
          <SessionRail
            sessions={sessions}
            selectedId={selectedSessionId}
            onSelect={handleSelectSession}
            onNewQuestion={handleNewQuestion}
            isCreating={createSession.isPending}
          />
        </aside>

        {/* Conversation column */}
        <div className="flex-1 flex flex-col min-w-0">
          {selectedSessionId ? (
            <ConversationWithScope
              key={selectedSessionId}
              sessionId={selectedSessionId}
              scope={scope}
              onScopeChange={setScope}
            />
          ) : (
            <div className="flex-1 flex items-center justify-center text-text-muted">
              <div className="text-center px-4">
                <MessagesSquare size={48} strokeWidth={1} className="mx-auto mb-4 opacity-30" aria-hidden />
                <p className="text-lg font-medium mb-2 text-text">Ask your lectures anything</p>
                <p className="text-sm mb-4">
                  Answers come from your own material, with citations to the source weeks.
                </p>
                <Button onClick={handleNewQuestion} loading={createSession.isPending}>
                  New question
                </Button>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Mobile sessions Sheet */}
      <Sheet open={mobileSessionsOpen} onOpenChange={setMobileSessionsOpen} side="right" title="Sessions">
        <SessionRail
          sessions={sessions}
          selectedId={selectedSessionId}
          onSelect={handleSelectSession}
          onNewQuestion={handleNewQuestion}
          isCreating={createSession.isPending}
        />
      </Sheet>
    </div>
  )
}

function ConversationWithScope({
  sessionId,
  scope,
  onScopeChange,
}: {
  sessionId: string
  scope: AskScope
  onScopeChange: (scope: AskScope) => void
}) {
  const { data: messagesData, isLoading } = useChatMessages(sessionId)
  const messages = useMemo(() => messagesData?.messages ?? [], [messagesData])
  const { isStreaming, streamingText, error, sendStreaming } = useStreamingChat(sessionId)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages.length, isStreaming, streamingText])

  return (
    <>
      <div className="flex-1 overflow-y-auto px-3 sm:px-6 py-5">
        {isLoading ? (
          <div className="space-y-5 max-w-3xl mx-auto animate-pulse" aria-label="Loading conversation">
            <div className="h-10 w-2/3 ml-auto rounded-xl bg-surface-2" />
            <div className="h-32 w-full rounded-xl bg-surface-2" />
          </div>
        ) : messages.length === 0 && !isStreaming ? (
          <EmptyState
            icon="?"
            title="Ask your first question"
            description="Answers come from your own lecture material, with citations. Scope to a course or week for sharper retrieval."
          />
        ) : (
          <div className="space-y-5 max-w-3xl mx-auto w-full">
            {messages.map((msg) => (
              <ChatMessage key={msg.id} message={msg} />
            ))}
            {isStreaming && streamingText && <StreamingMessage text={streamingText} />}
            <div ref={bottomRef} />
          </div>
        )}
      </div>

      {error && (
        <div className="mx-3 sm:mx-6 mb-2 px-3 py-2 rounded-lg bg-red-soft text-red-fg text-sm" role="alert">
          Failed to send: {error}
        </div>
      )}

      <AskComposer
        scope={scope}
        onScopeChange={onScopeChange}
        onSend={(content) => sendStreaming(content, scope)}
        disabled={isStreaming}
      />
    </>
  )
}
