import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { AssessmentTable } from '../components/courseops/AssessmentTable'
import { DeadlineTimeline } from '../components/courseops/DeadlineTimeline'
import { DocumentUpload } from '../components/courseops/DocumentUpload'
import { useAssessments, useCourseDocuments, useDeadlines } from '../hooks/useApi'
import { courseopsApi } from '../api/endpoints'
import type { CourseDocument } from '../types'

const TABS = ['Documents', 'Assessments', 'Deadlines', 'Exports'] as const
type Tab = (typeof TABS)[number]

const STATUS_COLORS: Record<string, string> = {
  pending: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-950 dark:text-yellow-400',
  processing: 'bg-blue-100 text-blue-700 dark:bg-blue-950 dark:text-blue-400',
  processed: 'bg-green-100 text-green-700 dark:bg-green-950 dark:text-green-400',
  failed: 'bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-400',
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function DocumentList({ documents, isLoading }: { documents: CourseDocument[]; isLoading: boolean }) {
  if (isLoading) {
    return <div className="py-4 text-center text-sm text-text-muted">Loading documents...</div>
  }

  if (documents.length === 0) {
    return null
  }

  return (
    <div className="mt-4 divide-y divide-border rounded-lg border border-border">
      {documents.map((doc) => (
        <div key={doc.id} className="flex items-center justify-between px-4 py-3">
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium text-text">{doc.original_filename}</p>
            <p className="text-xs text-text-muted">
              {doc.document_type} &middot; {formatBytes(doc.file_size_bytes)} &middot;{' '}
              {new Date(doc.created_at).toLocaleDateString()}
            </p>
          </div>
          <span
            className={`ml-3 inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${
              STATUS_COLORS[doc.status] ?? STATUS_COLORS.pending
            }`}
          >
            {doc.status}
          </span>
        </div>
      ))}
    </div>
  )
}

export function CourseOpsPage() {
  const { courseCode } = useParams<{ courseCode: string }>()
  const [activeTab, setActiveTab] = useState<Tab>('Documents')

  const documentsQuery = useCourseDocuments(courseCode ?? '')
  const assessmentsQuery = useAssessments(courseCode ?? '')
  const deadlinesQuery = useDeadlines(courseCode ?? '')

  if (!courseCode) {
    return <div className="p-6 text-red-600">Missing course code</div>
  }

  return (
    <div className="mx-auto max-w-5xl p-6">
      {/* Breadcrumb */}
      <nav className="mb-4 text-sm text-text-muted">
        <Link to="/" className="hover:text-blue-600">
          Dashboard
        </Link>
        {' / '}
        <Link to={`/courses/${courseCode}`} className="hover:text-blue-600">
          {courseCode}
        </Link>
        {' / '}
        <span className="text-text">Course Docs</span>
      </nav>

      <h1 className="mb-6 text-2xl font-bold text-text">{courseCode} — Course Documents</h1>

      {/* Tab bar */}
      <div className="mb-6 border-b border-border">
        <nav className="-mb-px flex gap-6">
          {TABS.map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`border-b-2 pb-3 text-sm font-medium transition-colors ${
                activeTab === tab
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-text-muted hover:border-border hover:text-text'
              }`}
            >
              {tab}
            </button>
          ))}
        </nav>
      </div>

      {/* Tab content */}
      {activeTab === 'Documents' && (
        <div>
          <DocumentUpload courseCode={courseCode} />
          <DocumentList documents={documentsQuery.data ?? []} isLoading={documentsQuery.isLoading} />
        </div>
      )}

      {activeTab === 'Assessments' && (
        <AssessmentTable
          assessments={assessmentsQuery.data ?? []}
          isLoading={assessmentsQuery.isLoading}
        />
      )}

      {activeTab === 'Deadlines' && (
        <DeadlineTimeline
          deadlines={deadlinesQuery.data ?? []}
          isLoading={deadlinesQuery.isLoading}
        />
      )}

      {activeTab === 'Exports' && (
        <div className="space-y-4">
          <p className="text-sm text-text-muted">
            Export deadlines and assessments for {courseCode}.
          </p>
          <div className="flex flex-wrap gap-3">
            <a
              href={courseopsApi.calendarUrl(courseCode)}
              download
              className="inline-flex items-center gap-2 rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
            >
              <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
              </svg>
              Download .ics Calendar
            </a>
            <a
              href={courseopsApi.taskPlanUrl(courseCode)}
              download
              className="inline-flex items-center gap-2 rounded-md bg-gray-600 px-4 py-2 text-sm font-medium text-white hover:bg-gray-700"
            >
              <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              Download Task Plan (.md)
            </a>
          </div>
        </div>
      )}
    </div>
  )
}
