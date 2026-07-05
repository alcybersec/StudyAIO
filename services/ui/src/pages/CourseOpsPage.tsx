import { useParams } from 'react-router-dom'
import { CalendarDays, FileText } from 'lucide-react'
import { AssessmentTable } from '../components/courseops/AssessmentTable'
import { DeadlineTimeline } from '../components/courseops/DeadlineTimeline'
import { DocumentList } from '../components/courseops/DocumentList'
import { DocumentUpload } from '../components/courseops/DocumentUpload'
import { EmptyState, PageHeader } from '../components/ui'
import { useAssessments, useCourseDocuments, useDeadlines } from '../hooks/useApi'
import { useTabRouting } from '../hooks/useTabRouting'
import { courseopsApi } from '../api/endpoints'

const TABS = ['documents', 'assessments', 'deadlines', 'exports'] as const

const TAB_LABELS: Record<(typeof TABS)[number], string> = {
  documents: 'Documents',
  assessments: 'Assessments',
  deadlines: 'Deadlines',
  exports: 'Exports',
}

export function CourseOpsPage() {
  const { courseCode } = useParams<{ courseCode: string }>()
  const [activeTab, setActiveTab] = useTabRouting(TABS, 'documents')

  const documentsQuery = useCourseDocuments(courseCode ?? '')
  const assessmentsQuery = useAssessments(courseCode ?? '')
  const deadlinesQuery = useDeadlines(courseCode ?? '')

  if (!courseCode) {
    return <EmptyState title="Missing course code" description="This page needs a course in the URL." actionLabel="Back to Dashboard" actionTo="/" />
  }

  return (
    <div className="mx-auto max-w-5xl">
      <PageHeader
        title={`${courseCode} — Course Documents`}
        breadcrumbs={[
          { label: 'Dashboard', to: '/' },
          { label: courseCode, to: `/courses/${courseCode}` },
          { label: 'Course Docs' },
        ]}
      />

      {/* Tab bar */}
      <div className="mb-6 border-b border-border">
        <nav className="-mb-px flex gap-6">
          {TABS.map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`border-b-2 pb-3 text-sm font-medium transition-colors ${
                activeTab === tab
                  ? 'border-peri text-text'
                  : 'border-transparent text-text-muted hover:border-border-strong hover:text-text'
              }`}
            >
              {TAB_LABELS[tab]}
            </button>
          ))}
        </nav>
      </div>

      {/* Tab content */}
      {activeTab === 'documents' && (
        <div>
          <DocumentUpload courseCode={courseCode} />
          <DocumentList
            documents={documentsQuery.data}
            isLoading={documentsQuery.isLoading}
            isError={documentsQuery.isError}
            onRetry={() => documentsQuery.refetch()}
          />
        </div>
      )}

      {activeTab === 'assessments' && (
        <AssessmentTable
          assessments={assessmentsQuery.data}
          isLoading={assessmentsQuery.isLoading}
          isError={assessmentsQuery.isError}
          onRetry={() => assessmentsQuery.refetch()}
        />
      )}

      {activeTab === 'deadlines' && (
        <DeadlineTimeline
          deadlines={deadlinesQuery.data}
          isLoading={deadlinesQuery.isLoading}
          isError={deadlinesQuery.isError}
          onRetry={() => deadlinesQuery.refetch()}
        />
      )}

      {activeTab === 'exports' && (
        <div className="space-y-4">
          <p className="text-sm text-text-muted">Export deadlines and assessments for {courseCode}.</p>
          <div className="flex flex-wrap gap-3">
            <a
              href={courseopsApi.calendarUrl(courseCode)}
              download
              className="inline-flex items-center gap-2 rounded-md bg-sage px-4 py-2 text-sm font-medium text-on-accent hover:bg-sage-hover transition-colors"
            >
              <CalendarDays size={14} aria-hidden />
              Download .ics Calendar
            </a>
            <a
              href={courseopsApi.taskPlanUrl(courseCode)}
              download
              className="inline-flex items-center gap-2 rounded-md bg-surface-2 px-4 py-2 text-sm font-medium text-text border border-border hover:bg-surface-2/70 transition-colors"
            >
              <FileText size={14} aria-hidden />
              Download Task Plan (.md)
            </a>
          </div>
        </div>
      )}
    </div>
  )
}
