import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { Button, Modal } from '../ui'

interface ConsentDialogProps {
  open: boolean
  busy: boolean
  /** The wording changed since this page loaded; the user is seeing it again. */
  changed: boolean
  /** A failed save, already translated. */
  error: string | null
  onAccept: () => void
  onDecline: () => void
}

/**
 * The AI-processing disclosure (api.ai-consent v1).
 *
 * "Not now" is always available: only the AI features need consent, and the
 * rest of the app keeps working without it.
 */
export function ConsentDialog({ open, busy, changed, error, onAccept, onDecline }: ConsentDialogProps) {
  const { t } = useTranslation()

  return (
    <Modal
      open={open}
      onOpenChange={(next) => {
        if (!next && !busy) onDecline()
      }}
      title={t('Before AI features run on your lectures')}
      description={t('Please read what is shared and agree to continue with AI features.')}
    >
      <div className="space-y-3 text-xs text-text-muted max-h-[60vh] overflow-y-auto">
        {changed && (
          <p role="status" className="rounded-lg bg-amber-soft text-amber-fg px-3 py-2">
            {t('This disclosure was updated. Please review it again.')}
          </p>
        )}
        <section>
          <h3 className="font-semibold text-text mb-1">{t('What is sent to the AI provider')}</h3>
          <ul className="list-disc pl-4 space-y-0.5">
            <li>{t('The text extracted from the lecture files you upload.')}</li>
            <li>{t('The questions you ask and your chat messages.')}</li>
          </ul>
        </section>
        <section>
          <h3 className="font-semibold text-text mb-1">{t('What is not sent')}</h3>
          <ul className="list-disc pl-4 space-y-0.5">
            <li>{t('Your password and your email address.')}</li>
            <li>{t('Other people\'s data: only your own content is ever used.')}</li>
          </ul>
        </section>
        <section>
          <h3 className="font-semibold text-text mb-1">{t('Why we ask')}</h3>
          <p>
            {t(
              'Summaries, chat answers, quizzes and flashcards are written by an AI provider, so they need this. Without your agreement those features stay off and the rest of the app keeps working.',
            )}
          </p>
        </section>
        <p>
          <Link
            to="/settings/privacy"
            onClick={onDecline}
            className="text-peri-fg underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-peri"
          >
            {t('Read more in Data & Privacy settings')}
          </Link>
        </p>
        {error && (
          <p role="alert" className="text-red-fg">
            {error}
          </p>
        )}
      </div>
      <div className="mt-4 flex flex-col-reverse sm:flex-row sm:justify-end gap-2">
        <Button variant="ghost" onClick={onDecline} disabled={busy} className="min-h-[44px]">
          {t('Not now')}
        </Button>
        <Button onClick={onAccept} loading={busy} className="min-h-[44px]">
          {t('I agree')}
        </Button>
      </div>
    </Modal>
  )
}
