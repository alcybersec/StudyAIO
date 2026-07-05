import { useRef, useState } from 'react'
import { Badge } from '../ui/Badge'
import type { ConceptNode } from '../../types'

type BadgeVariant = 'default' | 'success' | 'warning' | 'danger' | 'info'

const CATEGORY_VARIANTS: Record<string, BadgeVariant> = {
  theory: 'info',
  algorithm: 'warning',
  data_structure: 'success',
  pattern: 'info',
  tool: 'danger',
  language: 'info',
  protocol: 'info',
  principle: 'success',
  method: 'warning',
  general: 'default',
}

interface ConceptListProps {
  concepts: ConceptNode[]
  onSelect?: (conceptId: string) => void
  selectedId?: string | null
}

/**
 * Keyboard/screen-reader twin of the graph canvas. Roving tabindex: arrows
 * move focus between rows, Enter opens the focused concept's detail panel.
 */
export function ConceptList({ concepts, onSelect, selectedId }: ConceptListProps) {
  const [activeIndex, setActiveIndex] = useState(0)
  const rowRefs = useRef<(HTMLDivElement | null)[]>([])

  if (concepts.length === 0) {
    return (
      <div className="text-center py-8 text-sm text-text-muted">
        <p>No concepts found</p>
      </div>
    )
  }

  const clampedActive = Math.min(activeIndex, concepts.length - 1)

  const moveTo = (index: number) => {
    const next = Math.max(0, Math.min(concepts.length - 1, index))
    setActiveIndex(next)
    rowRefs.current[next]?.focus()
  }

  const handleKeyDown = (event: React.KeyboardEvent, index: number) => {
    switch (event.key) {
      case 'ArrowDown':
        event.preventDefault()
        moveTo(index + 1)
        break
      case 'ArrowUp':
        event.preventDefault()
        moveTo(index - 1)
        break
      case 'Home':
        event.preventDefault()
        moveTo(0)
        break
      case 'End':
        event.preventDefault()
        moveTo(concepts.length - 1)
        break
      case 'Enter':
      case ' ':
        event.preventDefault()
        onSelect?.(concepts[index].id)
        break
    }
  }

  return (
    <div role="listbox" aria-label="Concepts" className="divide-y divide-border">
      {concepts.map((concept, i) => {
        const selected = selectedId === concept.id
        return (
          <div
            key={concept.id}
            ref={(el) => {
              rowRefs.current[i] = el
            }}
            role="option"
            aria-selected={selected}
            tabIndex={i === clampedActive ? 0 : -1}
            onKeyDown={(e) => handleKeyDown(e, i)}
            onClick={() => {
              setActiveIndex(i)
              onSelect?.(concept.id)
            }}
            onFocus={() => setActiveIndex(i)}
            className={`flex items-center gap-3 py-2.5 px-2 text-[13px] cursor-pointer rounded-sm transition-colors focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-peri ${
              selected ? 'bg-surface-2' : 'hover:bg-surface-2/50'
            }`}
          >
            <span className="flex-1 min-w-0 truncate font-medium text-text">{concept.name}</span>
            <Badge variant={CATEGORY_VARIANTS[concept.category] ?? 'default'}>
              {concept.category.replace('_', ' ')}
            </Badge>
            <span className="font-mono text-[10px] text-text-faint w-12 text-right shrink-0">
              {concept.mention_count}×
            </span>
            <span className="font-mono text-[10px] text-text-faint w-20 text-right shrink-0 truncate">
              {concept.source_weeks.length > 0
                ? `wk ${[...concept.source_weeks].sort((a, b) => a - b).join(', ')}`
                : '—'}
            </span>
          </div>
        )
      })}
    </div>
  )
}
