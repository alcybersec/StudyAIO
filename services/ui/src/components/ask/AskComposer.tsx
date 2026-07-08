import { useCallback, useRef, type KeyboardEvent } from 'react'
import { SendHorizonal, X } from 'lucide-react'
import { useCourses } from '../../hooks/useApi'
import { Badge } from '../ui/Badge'
import { Button } from '../ui/Button'
import { Dropdown, DropdownItem } from '../ui/Dropdown'

export interface AskScope {
  courseCode: string | null
  week: number | null
}

interface AskComposerProps {
  scope: AskScope
  onScopeChange: (scope: AskScope) => void
  onSend: (content: string) => void
  disabled?: boolean
  /** Prefills the textarea on mount (e.g. a query handed over from the command palette). */
  initialValue?: string
}

/** Composer with course/week scope chips — chips narrow RAG retrieval. */
export function AskComposer({
  scope,
  onScopeChange,
  onSend,
  disabled = false,
  initialValue,
}: AskComposerProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const { data: courses } = useCourses()

  const scopedCourse = (courses ?? []).find((c) => c.code === scope.courseCode)
  const weekOptions = scopedCourse
    ? Array.from({ length: scopedCourse.weeks_covered }, (_, i) => i + 1)
    : []

  const adjustHeight = useCallback(() => {
    const textarea = textareaRef.current
    if (!textarea) return
    textarea.style.height = 'auto'
    textarea.style.height = `${Math.min(textarea.scrollHeight, 96)}px`
  }, [])

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
    <div className="border-t border-border bg-surface-1 p-3 sm:p-4">
      {/* Scope chips */}
      <div className="flex items-center flex-wrap gap-1.5 mb-2.5">
        {scope.courseCode && (
          <Badge variant="success">
            {scope.courseCode}
            <button
              type="button"
              aria-label="Remove course scope"
              onClick={() => onScopeChange({ courseCode: null, week: null })}
              className="ml-1 -mr-0.5 rounded-sm hover:opacity-70 cursor-pointer"
            >
              <X size={10} aria-hidden />
            </button>
          </Badge>
        )}
        {scope.courseCode && scope.week != null && (
          <Badge variant="success">
            Week {scope.week}
            <button
              type="button"
              aria-label="Remove week scope"
              onClick={() => onScopeChange({ ...scope, week: null })}
              className="ml-1 -mr-0.5 rounded-sm hover:opacity-70 cursor-pointer"
            >
              <X size={10} aria-hidden />
            </button>
          </Badge>
        )}
        {!scope.courseCode && (
          <Dropdown
            align="start"
            trigger={
              <button
                type="button"
                className="text-[11px] text-text-faint hover:text-text-muted transition-colors cursor-pointer"
              >
                + scope
              </button>
            }
          >
            {(courses ?? []).map((course) => (
              <DropdownItem
                key={course.id}
                onSelect={() => onScopeChange({ courseCode: course.code, week: null })}
              >
                {course.code}
              </DropdownItem>
            ))}
            {(courses ?? []).length === 0 && <DropdownItem disabled>No courses yet</DropdownItem>}
          </Dropdown>
        )}
        {scope.courseCode && scope.week == null && weekOptions.length > 0 && (
          <Dropdown
            align="start"
            trigger={
              <button
                type="button"
                className="text-[11px] text-text-faint hover:text-text-muted transition-colors cursor-pointer"
              >
                + week
              </button>
            }
          >
            {weekOptions.map((week) => (
              <DropdownItem key={week} onSelect={() => onScopeChange({ ...scope, week })}>
                Week {week}
              </DropdownItem>
            ))}
          </Dropdown>
        )}
      </div>

      {/* Input row */}
      <div className="flex items-end gap-2">
        <textarea
          ref={textareaRef}
          aria-label="Ask anything about your lectures"
          defaultValue={initialValue}
          onChange={adjustHeight}
          onKeyDown={handleKeyDown}
          disabled={disabled}
          placeholder={disabled ? 'Waiting for response…' : 'Ask anything about your lectures…'}
          rows={1}
          className="flex-1 resize-none rounded-xl border border-border bg-surface-0 px-4 py-2.5 text-sm text-text placeholder:text-text-faint focus:outline-none focus-visible:outline-2 focus-visible:outline-peri disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          style={{ minHeight: '42px', maxHeight: '96px' }}
        />
        <Button size="md" aria-label="Send" onClick={handleSend} disabled={disabled}>
          <SendHorizonal size={14} aria-hidden />
        </Button>
      </div>
      <p className="text-[10px] text-text-faint font-mono mt-2">
        answers cite their source weeks · scope chips narrow retrieval
      </p>
    </div>
  )
}
