import { useConceptDetail, useRelatedConcepts } from '../../hooks/useApi'

const RELATION_LABELS: Record<string, string> = {
  prerequisite: 'Prerequisite for',
  extends: 'Extends',
  uses: 'Uses',
  related_to: 'Related to',
  part_of: 'Part of',
}

const CATEGORY_BADGES: Record<string, string> = {
  theory: 'bg-indigo-100 text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-300',
  algorithm: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300',
  data_structure: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300',
  pattern: 'bg-violet-100 text-violet-700 dark:bg-violet-900/30 dark:text-violet-300',
  tool: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300',
  language: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300',
  protocol: 'bg-pink-100 text-pink-700 dark:bg-pink-900/30 dark:text-pink-300',
  principle: 'bg-teal-100 text-teal-700 dark:bg-teal-900/30 dark:text-teal-300',
  method: 'bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-300',
  general: 'bg-gray-100 text-gray-700 dark:bg-gray-900/30 dark:text-gray-300',
}

interface ConceptDetailProps {
  conceptId: string
  onNavigate?: (conceptId: string) => void
  onClose?: () => void
}

export function ConceptDetailPanel({ conceptId, onNavigate, onClose }: ConceptDetailProps) {
  const { data: concept, isLoading } = useConceptDetail(conceptId)
  const { data: related } = useRelatedConcepts(conceptId)

  if (isLoading) {
    return (
      <div className="p-4 space-y-3 animate-pulse">
        <div className="h-6 bg-surface-alt rounded w-3/4" />
        <div className="h-4 bg-surface-alt rounded w-full" />
        <div className="h-4 bg-surface-alt rounded w-2/3" />
      </div>
    )
  }

  if (!concept) {
    return <div className="p-4 text-text-muted">Concept not found</div>
  }

  const badgeClass = CATEGORY_BADGES[concept.category] || CATEGORY_BADGES.general

  return (
    <div className="p-4 space-y-4 overflow-y-auto max-h-[calc(100vh-200px)]">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h3 className="text-lg font-semibold text-text">{concept.name}</h3>
          <span className={`inline-block mt-1 px-2 py-0.5 rounded-full text-xs font-medium ${badgeClass}`}>
            {concept.category.replace('_', ' ')}
          </span>
        </div>
        {onClose && (
          <button
            onClick={onClose}
            className="text-text-muted hover:text-text p-1"
            aria-label="Close"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        )}
      </div>

      {/* Description */}
      <p className="text-sm text-text-muted">{concept.description}</p>

      {/* Metadata */}
      <div className="flex gap-4 text-xs text-text-muted">
        <span>Mentioned {concept.mention_count}x</span>
        {concept.source_weeks.length > 0 && (
          <span>Weeks: {concept.source_weeks.sort((a, b) => a - b).join(', ')}</span>
        )}
      </div>

      {/* Outgoing Relations */}
      {concept.outgoing_relations.length > 0 && (
        <div>
          <h4 className="text-sm font-medium text-text mb-2">Relationships</h4>
          <ul className="space-y-1.5">
            {concept.outgoing_relations.map((rel) => (
              <li key={rel.id} className="flex items-center gap-2 text-sm">
                <span className="text-text-muted text-xs shrink-0">
                  {RELATION_LABELS[rel.relation_type] || rel.relation_type}
                </span>
                <button
                  onClick={() => onNavigate?.(rel.concept_id)}
                  className="text-primary hover:underline truncate"
                >
                  {rel.concept_name}
                </button>
                <span className="ml-auto text-xs text-text-muted">
                  {Math.round(rel.confidence * 100)}%
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Incoming Relations */}
      {concept.incoming_relations.length > 0 && (
        <div>
          <h4 className="text-sm font-medium text-text mb-2">Referenced by</h4>
          <ul className="space-y-1.5">
            {concept.incoming_relations.map((rel) => (
              <li key={rel.id} className="flex items-center gap-2 text-sm">
                <button
                  onClick={() => onNavigate?.(rel.concept_id)}
                  className="text-primary hover:underline truncate"
                >
                  {rel.concept_name}
                </button>
                <span className="text-text-muted text-xs">
                  ({RELATION_LABELS[rel.relation_type] || rel.relation_type})
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Semantically Similar */}
      {related && related.length > 0 && (
        <div>
          <h4 className="text-sm font-medium text-text mb-2">Semantically Similar</h4>
          <ul className="space-y-1.5">
            {related.map((sim) => (
              <li key={sim.id} className="flex items-center gap-2 text-sm">
                <button
                  onClick={() => onNavigate?.(sim.id)}
                  className="text-primary hover:underline truncate"
                >
                  {sim.name}
                </button>
                <span className="ml-auto text-xs text-text-muted">
                  {Math.round(sim.similarity * 100)}%
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
