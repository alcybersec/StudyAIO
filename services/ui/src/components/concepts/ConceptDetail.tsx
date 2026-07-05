import { useMemo } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { BookOpen, Sparkles, X } from 'lucide-react'
import { Badge } from '../ui/Badge'
import { Button } from '../ui/Button'
import { SectionLabel } from '../ui/SectionLabel'
import { Skeleton } from '../ui/Skeleton'
import { useConceptDetail, useCourses, useRelatedConcepts } from '../../hooks/useApi'

const RELATION_LABELS: Record<string, string> = {
  prerequisite: 'prerequisite for',
  extends: 'extends',
  uses: 'uses',
  related_to: 'related to',
  part_of: 'part of',
}

interface ConceptDetailProps {
  conceptId: string
  onNavigate?: (conceptId: string) => void
  onClose?: () => void
}

interface RelatedChip {
  id: string
  name: string
  hint?: string
}

function ChipRow({ chips, onNavigate }: { chips: RelatedChip[]; onNavigate?: (id: string) => void }) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {chips.map((chip) => (
        <button
          key={chip.id}
          type="button"
          onClick={() => onNavigate?.(chip.id)}
          title={chip.hint}
          className="text-[11px] font-medium bg-surface-2 text-text-muted hover:text-text border border-transparent hover:border-border rounded-md px-2 py-0.5 cursor-pointer transition-colors"
        >
          {chip.name}
        </button>
      ))}
    </div>
  )
}

export function ConceptDetailPanel({ conceptId, onNavigate, onClose }: ConceptDetailProps) {
  const navigate = useNavigate()
  const { data: concept, isLoading } = useConceptDetail(conceptId)
  const { data: related } = useRelatedConcepts(conceptId)
  const { data: courses } = useCourses()

  const courseCode = useMemo(
    () => courses?.find((c) => c.id === concept?.course_id)?.code,
    [courses, concept],
  )

  const relatedChips = useMemo<RelatedChip[]>(() => {
    if (!concept) return []
    const seen = new Set<string>()
    const chips: RelatedChip[] = []
    for (const rel of [...concept.outgoing_relations, ...concept.incoming_relations]) {
      if (seen.has(rel.concept_id)) continue
      seen.add(rel.concept_id)
      chips.push({
        id: rel.concept_id,
        name: rel.concept_name,
        hint: RELATION_LABELS[rel.relation_type] ?? rel.relation_type,
      })
    }
    return chips
  }, [concept])

  if (isLoading) {
    return (
      <div className="space-y-3">
        <Skeleton height={16} width="40%" />
        <Skeleton height={20} width="70%" />
        <Skeleton height={48} width="100%" />
        <Skeleton height={32} width="100%" />
      </div>
    )
  }

  if (!concept) {
    return <p className="text-sm text-text-muted">Concept not found</p>
  }

  const weeks = [...concept.source_weeks].sort((a, b) => a - b)
  const studyWeek = weeks[0]

  return (
    <div className="space-y-4">
      <div>
        <div className="flex items-center justify-between gap-2">
          <SectionLabel className="mb-0">Selected concept</SectionLabel>
          {onClose && (
            <button
              type="button"
              onClick={onClose}
              className="text-text-faint hover:text-text p-1 rounded-md cursor-pointer transition-colors"
              aria-label="Close concept detail"
            >
              <X size={14} aria-hidden />
            </button>
          )}
        </div>
        <div className="flex items-center justify-between gap-2 mt-1">
          <h2 className="text-sm font-semibold text-text">{concept.name}</h2>
          <Badge variant="success">{courseCode ?? concept.category.replace('_', ' ')}</Badge>
        </div>
        <p className="text-xs text-text-muted mt-2 leading-relaxed">{concept.description}</p>
        <p className="font-mono text-[10px] text-text-faint mt-2">
          {concept.category.replace('_', ' ')} · mentioned {concept.mention_count}×
        </p>
      </div>

      {relatedChips.length > 0 && (
        <div>
          <SectionLabel>Related concepts</SectionLabel>
          <ChipRow chips={relatedChips} onNavigate={onNavigate} />
        </div>
      )}

      {related && related.length > 0 && (
        <div>
          <SectionLabel>Semantically similar</SectionLabel>
          <ChipRow
            chips={related.map((s) => ({
              id: s.id,
              name: s.name,
              hint: `${Math.round(s.similarity * 100)}% similar`,
            }))}
            onNavigate={onNavigate}
          />
        </div>
      )}

      {weeks.length > 0 && (
        <div>
          <SectionLabel>Appears in</SectionLabel>
          <ul className="text-xs space-y-1.5">
            {weeks.map((week) => (
              <li key={week}>
                {courseCode ? (
                  <Link
                    to={`/courses/${courseCode}/weeks/${week}`}
                    className="flex items-center gap-2 text-text-muted hover:text-text transition-colors"
                  >
                    <BookOpen size={12} className="text-text-faint shrink-0" aria-hidden />
                    <span className="underline decoration-border-strong underline-offset-2">
                      Week {week}
                    </span>
                  </Link>
                ) : (
                  <span className="flex items-center gap-2 text-text-muted">
                    <BookOpen size={12} className="text-text-faint shrink-0" aria-hidden />
                    Week {week}
                  </span>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      <Button
        size="sm"
        className="w-full"
        disabled={!courseCode || studyWeek === undefined}
        onClick={() => {
          if (!courseCode || studyWeek === undefined) return
          navigate(`/study?tab=flashcards&course=${courseCode}&week=${studyWeek}`)
        }}
      >
        <Sparkles size={13} aria-hidden /> Study this
      </Button>
    </div>
  )
}
