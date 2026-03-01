import { Link } from 'react-router-dom'
import { Card } from '../ui'
import type { CourseListItem } from '../../types'

function relativeDate(dateStr: string | null): string {
  if (!dateStr) return 'No activity'
  const iso = dateStr.endsWith('Z') ? dateStr : dateStr + 'Z'
  const diff = Date.now() - new Date(iso).getTime()
  const days = Math.floor(diff / 86_400_000)
  if (days === 0) return 'Updated today'
  if (days === 1) return 'Updated yesterday'
  if (days < 30) return `Updated ${days}d ago`
  return `Updated ${Math.floor(days / 30)}mo ago`
}

interface CourseCardProps {
  course: CourseListItem
}

export function CourseCard({ course }: CourseCardProps) {
  return (
    <Link to={`/courses/${course.code}`} className="block group">
      <Card className="group-hover:border-primary/30 group-hover:shadow-md transition-all">
        <div className="flex items-start justify-between mb-3">
          <div>
            <h3 className="text-lg font-bold text-gray-900 group-hover:text-primary transition-colors">
              {course.code}
            </h3>
            {course.name && (
              <p className="text-sm text-gray-500 mt-0.5">{course.name}</p>
            )}
          </div>
          <span className="text-2xl opacity-60">{'\u{1F4D6}'}</span>
        </div>
        <div className="flex items-center gap-4 text-sm text-gray-500">
          <span>{course.weeks_covered} week{course.weeks_covered !== 1 ? 's' : ''}</span>
          <span className="text-gray-300">|</span>
          <span>{course.total_artifacts} file{course.total_artifacts !== 1 ? 's' : ''}</span>
        </div>
        <p className="text-xs text-gray-400 mt-3">{relativeDate(course.last_updated)}</p>
      </Card>
    </Link>
  )
}
