import type { ConceptNode } from '../../types'

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

interface ConceptListProps {
  concepts: ConceptNode[]
  onSelect?: (conceptId: string) => void
  selectedId?: string | null
}

export function ConceptList({ concepts, onSelect, selectedId }: ConceptListProps) {
  if (concepts.length === 0) {
    return (
      <div className="text-center py-8 text-text-muted">
        <p>No concepts found</p>
      </div>
    )
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border text-left">
            <th className="pb-2 font-medium text-text-muted">Name</th>
            <th className="pb-2 font-medium text-text-muted">Category</th>
            <th className="pb-2 font-medium text-text-muted text-center">Mentions</th>
            <th className="pb-2 font-medium text-text-muted">Weeks</th>
          </tr>
        </thead>
        <tbody>
          {concepts.map((concept) => {
            const badgeClass = CATEGORY_BADGES[concept.category] || CATEGORY_BADGES.general
            return (
              <tr
                key={concept.id}
                onClick={() => onSelect?.(concept.id)}
                className={`border-b border-border/50 cursor-pointer transition-colors ${
                  selectedId === concept.id
                    ? 'bg-primary/5'
                    : 'hover:bg-surface-alt'
                }`}
              >
                <td className="py-2.5 pr-4">
                  <span className="font-medium text-text">{concept.name}</span>
                </td>
                <td className="py-2.5 pr-4">
                  <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${badgeClass}`}>
                    {concept.category.replace('_', ' ')}
                  </span>
                </td>
                <td className="py-2.5 text-center text-text-muted">
                  {concept.mention_count}
                </td>
                <td className="py-2.5 text-text-muted text-xs">
                  {concept.source_weeks.sort((a, b) => a - b).join(', ') || '—'}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
