import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import type { ChatAction } from '../../types'

interface ChatActionButtonProps {
  action: ChatAction
}

/** Study Hub exam builder URL with course and week preselected. */
function quizBuilderHref(action: ChatAction): string {
  const params = new URLSearchParams({ tab: 'exams', create: '1' })
  if (action.course_code) params.set('course', action.course_code)
  if (action.week != null) params.set('week', String(action.week))
  return `/study?${params.toString()}`
}

export function ChatActionButton({ action }: ChatActionButtonProps) {
  const { t } = useTranslation()

  if (action.type !== 'open_quiz_builder') return null

  let label = t('Open quiz builder')
  if (action.course_code && action.week != null) {
    label = t('Open quiz builder for {{course}} Week {{week}}', {
      course: action.course_code,
      week: action.week,
    })
  } else if (action.course_code) {
    label = t('Open quiz builder for {{course}}', { course: action.course_code })
  }

  return (
    <div className="mt-3">
      <Link
        to={quizBuilderHref(action)}
        className="inline-flex items-center min-h-[44px] px-4 py-2.5 rounded-lg text-sm font-medium bg-sage text-on-accent hover:bg-sage-hover transition-colors"
      >
        {label}
      </Link>
    </div>
  )
}
