import { useState, useEffect, useMemo } from 'react'
import { useSearchParams } from 'react-router-dom'
import { SessionList } from '../components/chat/SessionList'
import { ChatWindow } from '../components/chat/ChatWindow'
import { Sheet } from '../components/ui/Sheet'
import { useChatSessions, useCreateChatSession } from '../hooks/useApi'

export function ChatPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const selectedSessionId = searchParams.get('session') || ''
  const [mobileSessionsOpen, setMobileSessionsOpen] = useState(false)

  const { data: sessionsData } = useChatSessions()
  const sessions = useMemo(() => sessionsData?.sessions ?? [], [sessionsData])
  const createSession = useCreateChatSession()

  const handleSelectSession = (id: string) => {
    setSearchParams({ session: id }, { replace: true })
    setMobileSessionsOpen(false)
  }

  const handleNewChat = () => {
    createSession.mutate({}, {
      onSuccess: (session) => {
        handleSelectSession(session.id)
      },
    })
  }

  // Auto-select first session if none selected
  useEffect(() => {
    if (!selectedSessionId && sessions.length > 0) {
      setSearchParams({ session: sessions[0].id }, { replace: true })
    }
  }, [sessions, selectedSessionId, setSearchParams])

  return (
    <div className="flex flex-col h-[calc(100vh-4rem)] lg:h-[calc(100vh-0px)]">
      {/* Mobile header with sessions toggle */}
      <div className="lg:hidden flex items-center justify-between px-4 py-2 border-b border-border">
        <h1 className="text-lg font-semibold text-text">Chat</h1>
        <button
          onClick={() => setMobileSessionsOpen(true)}
          className="p-2 rounded-lg text-text-muted hover:text-text hover:bg-surface-alt transition-colors min-h-[44px] min-w-[44px] flex items-center justify-center"
        >
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25h16.5" />
          </svg>
        </button>
      </div>

      <div className="flex flex-1 overflow-hidden">
        {/* Desktop sidebar */}
        <div className="hidden lg:flex flex-col w-72 border-r border-border bg-surface">
          <SessionList
            sessions={sessions}
            selectedId={selectedSessionId}
            onSelect={handleSelectSession}
            onNewChat={handleNewChat}
            isCreating={createSession.isPending}
          />
        </div>

        {/* Chat area */}
        <div className="flex-1 flex flex-col min-w-0">
          {selectedSessionId ? (
            <ChatWindow sessionId={selectedSessionId} />
          ) : (
            <div className="flex-1 flex items-center justify-center text-text-muted">
              <div className="text-center px-4">
                <svg className="w-16 h-16 mx-auto mb-4 opacity-30" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M7.5 8.25h9m-9 3H12m-9.75 1.51c0 1.6 1.123 2.994 2.707 3.227 1.129.166 2.27.293 3.423.379.35.026.67.21.865.501L12 21l2.755-4.133a1.14 1.14 0 01.865-.501 48.172 48.172 0 003.423-.379c1.584-.233 2.707-1.626 2.707-3.228V6.741c0-1.602-1.123-2.995-2.707-3.228A48.394 48.394 0 0012 3c-2.392 0-4.744.175-7.043.513C3.373 3.746 2.25 5.14 2.25 6.741v6.018z" />
                </svg>
                <p className="text-lg font-medium mb-2 text-text">Welcome to Study Chat</p>
                <p className="text-sm mb-4">Start a new conversation to get AI-powered study help</p>
                <button
                  onClick={handleNewChat}
                  disabled={createSession.isPending}
                  className="px-4 py-2.5 bg-primary text-white rounded-lg hover:opacity-90 transition-opacity disabled:opacity-50 min-h-[44px]"
                >
                  {createSession.isPending ? 'Creating...' : 'New Chat'}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Mobile sessions Sheet */}
      <Sheet open={mobileSessionsOpen} onOpenChange={setMobileSessionsOpen} side="right" title="Conversations">
        <SessionList
          sessions={sessions}
          selectedId={selectedSessionId}
          onSelect={handleSelectSession}
          onNewChat={handleNewChat}
          isCreating={createSession.isPending}
        />
      </Sheet>
    </div>
  )
}
