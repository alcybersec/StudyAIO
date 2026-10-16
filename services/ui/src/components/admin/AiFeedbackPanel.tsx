import { useTranslation } from 'react-i18next'
import { useAdminAiFeedback } from '../../hooks/useApi'
import { ErrorState, Skeleton } from '../ui'

const DAYS = 30
const UP_MARK = '\u25B2'
const DOWN_MARK = '\u25BC'

/** Counts keyed by a server-side name, largest first. */
function CountList({ title, counts, label }: { title: string; counts: Record<string, number>; label: (k: string) => string }) {
  const rows = Object.entries(counts).sort((a, b) => b[1] - a[1])
  if (rows.length === 0) return null
  return (
    <div>
      <h3 className="text-[11px] font-medium text-text-muted mb-1">{title}</h3>
      <ul className="space-y-0.5">
        {rows.map(([key, n]) => (
          <li key={key} className="flex items-center justify-between gap-3 text-xs">
            <span className="text-text">{label(key)}</span>
            <span className="tabular-nums text-text-muted">{n}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}

/** Up/down vote counts per target type, most-voted first. */
function VoteSplitList({
  title,
  votes,
  label,
}: {
  title: string
  votes: Record<string, { up: number; down: number }>
  label: (k: string) => string
}) {
  const { t } = useTranslation()
  const rows = Object.entries(votes).sort((a, b) => b[1].up + b[1].down - (a[1].up + a[1].down))
  if (rows.length === 0) return null
  return (
    <div>
      <h3 className="text-[11px] font-medium text-text-muted mb-1">{title}</h3>
      <ul className="space-y-0.5">
        {rows.map(([key, { up, down }]) => (
          <li key={key} className="flex items-center justify-between gap-3 text-xs">
            <span className="text-text">{label(key)}</span>
            <span className="flex gap-2 tabular-nums text-text-muted">
              <span aria-label={`${t('Helpful')}: ${up}`}>
                <span aria-hidden="true">{UP_MARK}</span> {up}
              </span>
              <span aria-label={`${t('Not helpful')}: ${down}`}>
                <span aria-hidden="true">{DOWN_MARK}</span> {down}
              </span>
            </span>
          </li>
        ))}
      </ul>
    </div>
  )
}

/** Read-only summary of thumbs up/down on AI output (api.ai_feedback v1). */
export function AiFeedbackPanel() {
  const { t } = useTranslation()
  const { data, isLoading, isError, refetch } = useAdminAiFeedback(DAYS)

  const reasonLabel = (k: string) => {
    switch (k) {
      case 'inaccurate':
        return t('Inaccurate')
      case 'not_in_my_lectures':
        return t('Not in my lectures')
      case 'unclear':
        return t('Unclear')
      case 'wrong_format':
        return t('Wrong format')
      case 'other':
        return t('Other')
      default:
        return k
    }
  }
  const typeLabel = (k: string) => {
    switch (k) {
      case 'summary':
        return t('Summaries')
      case 'answer':
      case 'chat_message':
        return t('Chat answers')
      case 'flashcard':
        return t('Flashcards')
      case 'quiz_question':
        return t('Quiz questions')
      default:
        return k
    }
  }
  const ratingLabel = (k: string) => {
    if (k === '1' || k === 'up') return t('Helpful')
    if (k === '-1' || k === 'down') return t('Not helpful')
    return k
  }

  if (isLoading) {
    return (
      <div className="bg-surface-1 rounded-xl border border-border p-4 space-y-3" aria-busy="true">
        <Skeleton height={12} width={140} />
        <Skeleton height={48} />
      </div>
    )
  }

  if (isError && !data) {
    return <ErrorState compact title={t("AI feedback couldn't load")} onRetry={() => refetch()} />
  }

  if (!data) return null

  return (
    <section className="bg-surface-1 rounded-xl border border-border p-4 space-y-3">
      <header>
        <h2 className="text-sm font-medium text-text">{t('AI feedback')}</h2>
        <p className="text-[11px] text-text-faint">{t('Last {{days}} days. No user identities are shown.', { days: DAYS })}</p>
      </header>

      {data.total === 0 ? (
        <p className="text-xs text-text-muted">{t('No AI feedback in this period yet.')}</p>
      ) : (
        <>
          <p className="text-2xl font-bold text-text tabular-nums">
            {data.total} <span className="text-xs font-normal text-text-muted">{t('votes')}</span>
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <CountList title={t('Rating')} counts={data.by_rating} label={ratingLabel} />
            <VoteSplitList title={t('By content')} votes={data.by_target_type} label={typeLabel} />
            <CountList title={t('Reasons for thumbs down')} counts={data.by_reason} label={reasonLabel} />
          </div>
          {data.recent_negative.length > 0 && (
            <div>
              <h3 className="text-[11px] font-medium text-text-muted mb-1">{t('Recent thumbs down')}</h3>
              <ul className="space-y-1.5">
                {data.recent_negative.map((n, i) => (
                  <li key={`${n.created_at}-${i}`} className="text-xs text-text break-words">
                    <span className="text-text-muted">
                      {typeLabel(n.target_type)}
                      {n.reason ? ` · ${reasonLabel(n.reason)}` : ''}
                      {' · '}
                      {new Date(n.created_at).toLocaleDateString()}
                    </span>
                    {n.comment && <p className="mt-0.5">{n.comment}</p>}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </>
      )}
    </section>
  )
}
