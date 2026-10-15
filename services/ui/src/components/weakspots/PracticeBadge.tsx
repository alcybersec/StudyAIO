import { useTranslation } from 'react-i18next'
import { Badge } from '../ui'

/** Marks an item generated from the student's own weak spots (origin=targeted). */
export function PracticeBadge() {
  const { t } = useTranslation()
  return <Badge variant="info">{t('Practice')}</Badge>
}
