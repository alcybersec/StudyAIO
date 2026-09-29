import { Badge, EmptyState, ErrorState, Skeleton, Table, TBody, TCell, THead, TRow } from '../ui'
import { useTranslation } from 'react-i18next'
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
  const { t } = useTranslation()

  return (
    <div className="space-y-3 py-2" role="status" aria-label={t('Loading assessments')}>
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
  const { t } = useTranslation()

  if (isLoading && !assessments) return <AssessmentTableSkeleton />

  if (isError && !assessments) {
    return <ErrorState title={t("Assessments couldn't load")} onRetry={onRetry} />
  }

  if (!assessments || assessments.length === 0) {
    return (
      <EmptyState
        title={t('No assessments extracted yet')}
        description={t('Upload a course outline in the Documents tab to get started.')}
      />
    )
  }

  const totalWeight = assessments.reduce((sum, a) => sum + (a.weight_pct ?? 0), 0)

  return (
    <Table>
      <THead>
        <TCell header className="w-[28%]">{t('Assessment')}</TCell>
        <TCell header className="w-[14%]">{t('Type')}</TCell>
        <TCell header className="w-[10%]">{t('Weight')}</TCell>
        <TCell header className="w-[12%]">{t('Weeks')}</TCell>
        <TCell header className="w-[26%]">{t('Description')}</TCell>
        <TCell header align="right" className="w-[10%]">
          {t('Docs')}
        </TCell>
      </THead>
      <TBody>
        {assessments.map((a) => (
          <TRow key={a.id} onClick={onSelect ? () => onSelect(a) : undefined}>
            <TCell className="font-medium text-text">{a.title}</TCell>
            <TCell>
              <Badge variant={TYPE_VARIANTS[a.assessment_type] ?? 'default'}>{a.assessment_type}</Badge>
            </TCell>
            <TCell className="font-mono text-text">
              {a.weight_pct != null ? `${a.weight_pct}%` : '—'}
            </TCell>
            <TCell className="font-mono text-[12px] text-text-muted">
              {a.weeks_relevant && a.weeks_relevant.length > 0 ? a.weeks_relevant.join(', ') : '—'}
            </TCell>
            <TCell className="max-w-0 truncate text-text-muted">{a.description ?? '—'}</TCell>
            <TCell align="right" className="text-xs text-peri-fg">
              {onSelect ? t('Manage →') : ''}
            </TCell>
          </TRow>
        ))}
        {totalWeight > 0 && (
          <TRow className="border-t border-border-strong">
            <TCell className="font-medium text-text">{t('Total')}</TCell>
            <TCell />
            <TCell className="font-mono font-medium text-text">{totalWeight}%</TCell>
            <TCell />
            <TCell />
            <TCell />
          </TRow>
        )}
      </TBody>
    </Table>
  )
}
