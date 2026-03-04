import { useRef, useCallback, type KeyboardEvent } from 'react'

interface ChatInputProps {
  onSend: (content: string) => void
  disabled?: boolean
}

export function ChatInput({ onSend, disabled = false }: ChatInputProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const adjustHeight = useCallback(() => {
    const textarea = textareaRef.current
    if (!textarea) return
    textarea.style.height = 'auto'
    const lineHeight = 24
    const maxLines = 4
    const maxHeight = lineHeight * maxLines
    textarea.style.height = `${Math.min(textarea.scrollHeight, maxHeight)}px`
  }, [])

  const handleChange = () => {
    adjustHeight()
  }

  const handleSend = () => {
    const textarea = textareaRef.current
    if (!textarea) return
    const content = textarea.value.trim()
    if (!content || disabled) return
    onSend(content)
    textarea.value = ''
    adjustHeight()
    textarea.focus()
  }

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div className="border-t border-border bg-surface p-3 sm:p-4">
      <div className="flex items-end gap-2">
        <textarea
          ref={textareaRef}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          disabled={disabled}
          placeholder={disabled ? 'Waiting for response...' : 'Ask a study question... (Enter to send, Shift+Enter for newline)'}
          rows={1}
          className="flex-1 resize-none rounded-lg border border-border bg-surface-alt px-3 py-2 text-sm text-text placeholder:text-text-muted focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          style={{ minHeight: '40px', maxHeight: '96px' }}
        />
        <button
          onClick={handleSend}
          disabled={disabled}
          className="shrink-0 h-10 w-10 flex items-center justify-center rounded-lg bg-primary text-white hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed transition-opacity"
          title="Send message"
        >
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M6 12L3.269 3.126A59.768 59.768 0 0121.485 12 59.77 59.77 0 013.27 20.876L5.999 12zm0 0h7.5" />
          </svg>
        </button>
      </div>
    </div>
  )
}
