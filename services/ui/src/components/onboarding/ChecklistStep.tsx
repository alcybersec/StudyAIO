import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Check } from 'lucide-react'
import type { StepStatus } from '../../lib/onboarding'

interface ChecklistStepProps {
  index: number
  title: string
  status: StepStatus
  children?: ReactNode
}

/** Shared look for a step's primary action, whether it renders as a link or a button. */
export const STEP_ACTION_CLASS =
  'inline-flex items-center justify-center min-h-[44px] md:min-h-0 px-3 py-1.5 rounded-md bg-sage text-on-accent text-xs font-medium hover:bg-sage-hover transition-colors cursor-pointer disabled:opacity-45 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-peri'

/** One row of the first-run checklist: a state marker, a title, and what to do about it. */
export function ChecklistStep({ index, title, status, children }: ChecklistStepProps) {
  const { t } = useTranslation()
  return (
    <li
      className="flex gap-3 py-2.5"
      aria-current={status === 'active' ? 'step' : undefined}
      data-status={status}
    >
      <span
        className={`mt-0.5 h-6 w-6 shrink-0 rounded-full border flex items-center justify-center text-[11px] font-mono ${
          status === 'done'
            ? 'bg-sage-soft border-sage/40 text-sage-fg'
            : status === 'active'
              ? 'border-sage text-text'
              : 'border-border text-text-faint'
        }`}
        aria-hidden
      >
        {status === 'done' ? <Check size={13} /> : index}
      </span>
      <div className="min-w-0 flex-1 space-y-1.5">
        <p className={`text-[13px] font-medium ${status === 'locked' ? 'text-text-muted' : 'text-text'}`}>
          {title}
          <span className="sr-only">
            {' — '}
            {status === 'done' ? t('done') : status === 'active' ? t('next') : t('not available yet')}
          </span>
        </p>
        {children}
      </div>
    </li>
  )
}
