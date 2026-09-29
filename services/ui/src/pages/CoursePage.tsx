import { useMemo, useState } from 'react'
import i18n from '../i18n'
import { useTranslation } from 'react-i18next'
import { useNavigate, useParams } from 'react-router-dom'
import { useArchiveCourse, useCourseDetail } from '../hooks/useApi'
import {
  Button,
  Card,
  EmptyState,
  ErrorState,
  PageHeader,
  Skeleton,
  TBody,
  TCell,
  THead,
  Table,
  toast,
} from '../components/ui'
import { toastMutationError } from '../lib/toast'
import { DeleteCourseModal } from '../components/course/DeleteCourseModal'
import { ManageMenu } from '../components/course/ManageMenu'
import { MergeCourseModal } from '../components/course/MergeCourseModal'
import { RenameCourseModal } from '../components/course/RenameCourseModal'
import { WeekRow } from '../components/course/WeekRow'

type CourseModal = 'rename' | 'merge' | 'delete' | null

function CourseSkeleton() {
  return (
    <div>
      <div className="mb-6 space-y-2">
        <Skeleton height={28} width={280} />
        <Skeleton height={14} width={200} />
      </div>
      <Card>
        <div className="space-y-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} height={20} />
          ))}
        </div>
      </Card>
    </div>
  )
}

export function CoursePage() {
  const { t } = useTranslation()

  const { courseCode } = useParams<{ courseCode: string }>()
  const navigate = useNavigate()
  const { data, isLoading, error, refetch } = useCourseDetail(courseCode ?? '')
  const [modal, setModal] = useState<CourseModal>(null)
  const archiveMutation = useArchiveCourse()

  const totalCards = useMemo(
    () => data?.weeks.reduce((sum, w) => sum + w.flashcard_count, 0) ?? 0,
    [data],
  )

  if (isLoading) return <CourseSkeleton />
  if (error) {
    return (
      <ErrorState
        title={t("Course couldn't load")}
        detail={error instanceof Error ? error.message : undefined}
        onRetry={() => refetch()}
      />
    )
  }
  if (!data) {
    return <EmptyState title={t('Course not found')} description={t('It may have been renamed or deleted.')} />
  }

  const { course, weeks } = data

  const handleArchive = () => {
    archiveMutation.mutate(course.code, {
      onSuccess: () => {
        toast.success(i18n.t('{{code}} archived — recoverable anytime', { code: course.code }))
        navigate('/')
      },
      onError: (err) => toastMutationError(err, handleArchive),
    })
  }

  return (
    <div>
      <PageHeader
        title={course.name ? `${course.code} — ${course.name}` : course.code}
        breadcrumbs={[{ label: 'Dashboard', to: '/' }, { label: course.code }]}
        subtitle={t('{{weeks}} weeks · {{cards}} cards', {
          weeks: weeks.length,
          cards: totalCards,
        })}
        actions={
          <>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => navigate(`/courses/${course.code}/ops`)}
            >
              {t('Course ops')}
            </Button>
            <Button size="sm" onClick={() => navigate(`/study?course=${course.code}`)}>
              {t('Study this course')}
            </Button>
            <ManageMenu
              courseCode={course.code}
              onRename={() => setModal('rename')}
              onMerge={() => setModal('merge')}
              onArchive={handleArchive}
              onDelete={() => setModal('delete')}
            />
          </>
        }
      />

      {weeks.length === 0 ? (
        <Card>
          <EmptyState
            title={t('No weeks yet')}
            description={t('Upload lectures for this course — weeks are created from classification.')}
            actionLabel={t('Upload lectures')}
            actionTo="/upload"
          />
        </Card>
      ) : (
        <Card className="px-4 py-2">
          <Table>
            <THead>
              <TCell header className="pl-1">
                {t('Week')}
              </TCell>
              <TCell header>{t('Topic')}</TCell>
              <TCell header align="right">
                {t('Cards')}
              </TCell>
              <TCell header align="right">
                {t('Due')}
              </TCell>
              <TCell header align="right">
                {t('Quiz')}
              </TCell>
              <TCell header align="right" className="pr-1">
                {t('Updated')}
              </TCell>
            </THead>
            <TBody>
              {weeks.map((week) => (
                <WeekRow key={week.week} courseCode={course.code} week={week} />
              ))}
            </TBody>
          </Table>
        </Card>
      )}

      <RenameCourseModal
        open={modal === 'rename'}
        onOpenChange={(open) => setModal(open ? 'rename' : null)}
        course={course}
      />
      <MergeCourseModal
        open={modal === 'merge'}
        onOpenChange={(open) => setModal(open ? 'merge' : null)}
        course={course}
      />
      <DeleteCourseModal
        open={modal === 'delete'}
        onOpenChange={(open) => setModal(open ? 'delete' : null)}
        course={course}
        weeks={weeks}
      />
    </div>
  )
}
