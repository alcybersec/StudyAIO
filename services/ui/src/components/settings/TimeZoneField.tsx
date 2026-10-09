import { useId, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Button, Input } from '../ui'
import { useSettings, useUpdateSettings } from '../../hooks/useApi'
import { ValidationError } from '../../api/errors'
import { listTimeZones, markTimeZoneChosen } from '../../lib/timezone'

/** Searchable time zone picker (type to filter the IANA list), saved explicitly. */
export function TimeZoneField() {
  const { t } = useTranslation()
  const listId = useId()
  const { data: settings, isLoading } = useSettings()
  const update = useUpdateSettings()
  const zones = useMemo(() => listTimeZones(), [])
  const [draft, setDraft] = useState<string | null>(null)
  const [fieldError, setFieldError] = useState<string | null>(null)

  const stored = settings?.timezone ?? ''
  const value = draft ?? stored
  const unchanged = value === stored

  const save = () => {
    setFieldError(null)
    update.mutate(
      { timezone: value },
      {
        onSuccess: () => {
          markTimeZoneChosen()
          setDraft(null)
        },
        onError: (err) => {
          if (err instanceof ValidationError) {
            setFieldError(err.fields.timezone || t('That time zone is not valid.'))
          } else {
            setFieldError(t("Couldn't save the time zone. Try again."))
          }
        },
      },
    )
  }

  return (
    <div>
      <div className="flex items-end gap-2">
        <Input
          className="flex-1"
          label={t('Time zone')}
          list={listId}
          value={value}
          disabled={isLoading || !settings}
          error={fieldError ?? undefined}
          autoComplete="off"
          spellCheck={false}
          onChange={(e) => {
            setDraft(e.target.value)
            setFieldError(null)
          }}
        />
        <Button
          size="sm"
          onClick={save}
          disabled={isLoading || !settings || unchanged || !value || update.isPending}
        >
          {update.isPending ? t('Saving…') : t('Save time zone')}
        </Button>
      </div>
      <datalist id={listId}>
        {zones.map((zone) => (
          <option key={zone} value={zone} />
        ))}
      </datalist>
      <p className="mt-1.5 text-xs text-text-faint">
        {t('Decides when your day starts: streaks, what is due today, and exam countdowns.')}
      </p>
    </div>
  )
}
