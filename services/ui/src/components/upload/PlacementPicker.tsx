import { useId, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Input, Select } from '../ui'
import { useCourses } from '../../hooks/useApi'
import { MAX_COURSE_CODE, type FieldErrors, type PlacementDraft } from '../../lib/studyItems'

interface PlacementPickerProps {
  value: PlacementDraft
  onChange: (next: PlacementDraft) => void
  errors: FieldErrors<'course' | 'week'>
  disabled?: boolean
}

const NEW_COURSE = '__new__'

/**
 * Optional "Course & week" control for uploads. Default is "Let StudyAIO
 * decide" (AI classification). Choosing a placement needs both a course and a
 * week; the pipeline then skips classification.
 */
export function PlacementPicker({ value, onChange, errors, disabled }: PlacementPickerProps) {
  const { t } = useTranslation()
  const groupId = useId()
  const { data: courses } = useCourses()
  const known = (courses ?? []).map((c) => c.code)
  const [creating, setCreating] = useState(false)
  const selectValue = creating ? NEW_COURSE : known.includes(value.course) ? value.course : ''
  const showCodeInput = known.length === 0 || creating

  const options = [
    ...(courses ?? []).map((c) => ({ value: c.code, label: c.name ? `${c.code} — ${c.name}` : c.code })),
    { value: NEW_COURSE, label: t('New course…') },
  ]

  return (
    <fieldset className="mb-4 rounded-xl border border-border bg-surface-1 px-4 py-3" disabled={disabled}>
      <legend className="px-1 text-xs font-medium text-text-muted">{t('Course & week')}</legend>
      <div role="radiogroup" aria-label={t('Course & week')} className="flex flex-wrap gap-2">
        {(['auto', 'manual'] as const).map((mode) => (
          <label
            key={mode}
            className={`flex items-center gap-2 px-4 min-h-11 rounded-full text-xs font-medium cursor-pointer focus-within:outline-2 focus-within:outline-peri ${
              value.mode === mode ? 'bg-peri-soft text-peri-fg' : 'bg-surface-2 text-text-muted hover:text-text'
            }`}
          >
            <input
              type="radio"
              name={`${groupId}-mode`}
              checked={value.mode === mode}
              onChange={() => onChange({ ...value, mode })}
              className="accent-[var(--color-sage)]"
            />
            {mode === 'auto' ? t('Let StudyAIO decide') : t('Choose course & week')}
          </label>
        ))}
      </div>

      {value.mode === 'manual' && (
        <div className="mt-3 grid grid-cols-1 sm:grid-cols-[1fr_1fr_120px] gap-3 items-start max-w-2xl">
          {known.length > 0 && (
            <Select
              label={t('Course')}
              options={options}
              value={selectValue}
              placeholder={t('Select course')}
              onValueChange={(v) => {
                setCreating(v === NEW_COURSE)
                onChange({ ...value, course: v === NEW_COURSE ? '' : v })
              }}
              error={!showCodeInput ? errors.course : undefined}
            />
          )}
          {showCodeInput && (
            <Input
              label={known.length > 0 ? t('New course code') : t('Course code')}
              value={value.course}
              maxLength={MAX_COURSE_CODE + 10}
              placeholder={t('e.g. CSIT302')}
              onChange={(e) => onChange({ ...value, course: e.target.value })}
              error={errors.course}
            />
          )}
          <Input
            label={t('Week')}
            inputMode="numeric"
            value={value.week}
            onChange={(e) => onChange({ ...value, week: e.target.value })}
            error={errors.week}
          />
        </div>
      )}
      <p className="text-[11px] text-text-faint mt-2">
        {value.mode === 'auto'
          ? t('The course and week are worked out from the file.')
          : t('The file goes straight to extraction; classification is skipped.')}
      </p>
    </fieldset>
  )
}
