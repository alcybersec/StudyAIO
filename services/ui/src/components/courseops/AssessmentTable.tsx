import { Badge, EmptyState, ErrorState, Skeleton, Table, TBody, TCell, THead, TRow } from '../ui'
import type { Assessment } from '../../types'

interface AssessmentTableProps {
  assessments: Assessment[] | undefined
  isLoading: boolean
  isError: boolean
  onRetry: () => void
  onSelect?: (assessment: Assessment) => void
}

type BadgeVariant = 'default' | 'success' | 'warning' | 'danger' | 'info'

const TYPE_VARIANTS: Record<string, BadgeVariant> = {
  exam: 'danger',
  assignment: 'info',
  quiz: 'warning',
  project: 'info',
  lab: 'success',
  presentation: 'warning',
  other: 'default',
}

function AssessmentTableSkeleton() {
  return (
    <div className="space-y-3 py-2" role="status" aria-label="Loading assessments">
      {Array.from({ length: 4 }).map((_, i) => (
        <div key={i} className="flex items-center gap-4">
          <Skeleton height={14} width="30%" />
          <Skeleton height={18} width={72} rounded />
          <Skeleton height={14} width={48} />
          <Skeleton height={14} width="25%" />
        </div>
      ))}
    </div>
  )
}

export function AssessmentTable({ assessments, isLoading, isError, onRetry, onSelect }: AssessmentTableProps) {
  if (isLoading && !assessments) return <AssessmentTableSkeleton />

  if (isError && !assessments) {
    return <ErrorState title="Assessments couldn't load" onRetry={onRetry} />
  }

  if (!assessments || assessments.length === 0) {
    return (
      <EmptyState
        title="No assessments extracted yet"
        description="Upload a course outline in the Documents tab to get started."
      />
    )
  }

  const totalWeight = assessments.reduce((sum, a) => sum + (a.weight_pct ?? 0), 0)

  return (
    <Table>
      <THead>
        <TCell header>Assessment</TCell>
        <TCell header>Type</TCell>
        <TCell header align="right">
          Weight
        </TCell>
        <TCell header>Weeks</TCell>
        <TCell header grow>
          Description
        </TCell>
        <TCell header align="right">
          Docs
        </TCell>
      </THead>
      <TBody>
        {assessments.map((a) => (
          <TRow key={a.id} onClick={onSelect ? () => onSelect(a) : undefined}>
            <TCell className="font-medium text-text">{a.title}</TCell>
            <TCell>
              <Badge variant={TYPE_VARIANTS[a.assessment_type] ?? 'default'}>{a.assessment_type}</Badge>
            </TCell>
            <TCell align="right" className="font-mono text-text">
              {a.weight_pct != null ? `${a.weight_pct}%` : '—'}
            </TCell>
            <TCell className="font-mono text-[12px] text-text-muted">
              {a.weeks_relevant && a.weeks_relevant.length > 0 ? a.weeks_relevant.join(', ') : '—'}
            </TCell>
            <TCell grow className="max-w-0 truncate text-text-muted">{a.description ?? '—'}</TCell>
            <TCell align="right" className="text-xs text-peri-fg">
              {onSelect ? 'Manage →' : ''}
            </TCell>
          </TRow>
        ))}
        {totalWeight > 0 && (
          <TRow className="border-t border-border-strong">
            <TCell className="font-medium text-text">Total</TCell>
            <TCell />
            <TCell align="right" className="font-mono font-medium text-text">
              {totalWeight}%
            </TCell>
            <TCell />
            <TCell />
            <TCell />
          </TRow>
        )}
      </TBody>
    </Table>
  )
}
