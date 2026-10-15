import { useTranslation } from 'react-i18next'
import { Badge } from '../ui'
import { PracticeBadge } from '../weakspots/PracticeBadge'
import type { ItemOrigin } from '../../types'

/** Origin marker for a card or question: "Practice" for targeted, "Yours" for hand-made or edited. */
export function OriginBadge({ origin }: { origin?: ItemOrigin }) {
  const { t } = useTranslation()
  if (origin === 'targeted') return <PracticeBadge />
  if (origin === 'user') return <Badge variant="success">{t('Yours')}</Badge>
  return null
}
