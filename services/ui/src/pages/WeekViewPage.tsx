import { useState, useEffect, useCallback, useMemo, useRef } from 'react'
import { useParams, useSearchParams } from 'react-router-dom'
import { useWeekDetail } from '../hooks/useApi'
import { LoadingSpinner, EmptyState, ErrorBanner, PageHeader, Card } from '../components/ui'
import { SummaryTab } from '../components/week/SummaryTab'
import { ArtifactList } from '../components/week/ArtifactList'
import { ScopedQA } from '../components/qa/ScopedQA'
import { FlashcardsTab } from '../components/week/FlashcardsTab'
import { QuizTab } from '../components/week/QuizTab'
import { FileViewer, FileViewerToolbar, ViewOriginalModal } from '../components/viewer'
import type { Artifact } from '../types'

type Tab = 'summary' | 'qa' | 'flashcards' | 'quiz'

const tabs: { id: Tab; label: string }[] = [
  { id: 'summary', label: 'Summary' },
  { id: 'qa', label: 'Q&A' },
  { id: 'flashcards', label: 'Flashcards' },
  { id: 'quiz', label: 'Quiz' },
]

export function WeekViewPage() {
  const { courseCode, weekNumber } = useParams<{ courseCode: string; weekNumber: string }>()
  const week = Number(weekNumber)
  const { data, isLoading, error, refetch } = useWeekDetail(courseCode ?? '', week)
  const [searchParams] = useSearchParams()
  const [activeTab, setActiveTab] = useState<Tab>('summary')

  // Viewer state
  const [selectedArtifactId, setSelectedArtifactId] = useState<string | null>(null)
  const [viewerTargetPage, setViewerTargetPage] = useState<number | undefined>()
  const [viewerCurrentPage, setViewerCurrentPage] = useState(1)
  const [viewerTotalPages, setViewerTotalPages] = useState(0)
  const [viewerOpen, setViewerOpen] = useState(false)
  const [mobileViewerOpen, setMobileViewerOpen] = useState(false)
  // Counter to force re-trigger scroll even when navigating to the same page number
  const navCounter = useRef(0)
  const [navToken, setNavToken] = useState(0)

  // Read URL params on mount for deep linking
  useEffect(() => {
    const artifactParam = searchParams.get('artifact')
    const pageParam = searchParams.get('page')
    if (artifactParam) {
      setSelectedArtifactId(artifactParam) // eslint-disable-line react-hooks/set-state-in-effect
      setViewerOpen(true)
    }
    if (pageParam) {
      setViewerTargetPage(Number(pageParam))
      setNavToken(++navCounter.current)
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // Default artifact selection: prefer first PDF, else first artifact
  useEffect(() => {
    if (!data?.artifacts.length || selectedArtifactId) return
    const firstPdf = data.artifacts.find((a) => a.file_type === 'pdf')
    setSelectedArtifactId(firstPdf?.id ?? data.artifacts[0].id) // eslint-disable-line react-hooks/set-state-in-effect
  }, [data?.artifacts, selectedArtifactId])

  const selectedArtifact = useMemo<Artifact | null>(() => { // eslint-disable-line react-hooks/preserve-manual-memoization
    if (!data?.artifacts.length || !selectedArtifactId) return null
    return data.artifacts.find((a) => a.id === selectedArtifactId) ?? null
  }, [data?.artifacts, selectedArtifactId])

  const handleSelectArtifact = useCallback((id: string) => {
    setSelectedArtifactId(id)
    setViewerTargetPage(undefined)
    setViewerCurrentPage(1)
    setViewerTotalPages(0)
  }, [])

  const handleGoToPage = useCallback((page: number) => {
    setViewerTargetPage(page)
    setViewerCurrentPage(page) // Immediately update counter so toolbar is responsive
    setNavToken(++navCounter.current)
  }, [])

  const handleCitationClick = useCallback((artifactId: string, page: number) => {
    setSelectedArtifactId(artifactId)
    setViewerTargetPage(page)
    setNavToken(++navCounter.current)
    setViewerOpen(true)
  }, [])

  if (isLoading) return <LoadingSpinner label="Loading week..." />
  if (error) return <ErrorBanner message="Failed to load week data." onRetry={refetch} />
  if (!data) return <EmptyState icon="?" title="Week not found" />

  const hasArtifacts = data.artifacts.length > 0

  return (
    <div>
      <PageHeader
        title={`Week ${data.week}`}
        subtitle={data.course.name ?? data.course.code}
        breadcrumbs={[
          { label: 'Dashboard', to: '/' },
          { label: data.course.code, to: `/courses/${courseCode}` },
          { label: `Week ${data.week}` },
        ]}
      />

      {/* Mobile: View Original button */}
      {hasArtifacts && (
        <div className="lg:hidden mb-4">
          <button
            onClick={() => setMobileViewerOpen(true)}
            className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-surface-alt border border-border rounded-lg text-sm font-medium text-text hover:bg-surface-alt transition-colors min-h-[44px]"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
              <path strokeLinecap="round" strokeLinejoin="round" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
            </svg>
            View Original
          </button>
        </div>
      )}

      {/* Split-panel layout: tabs left, viewer right (desktop) */}
      <div className={hasArtifacts && viewerOpen ? 'lg:grid lg:grid-cols-[minmax(400px,1.2fr)_minmax(300px,1fr)] lg:gap-6' : ''}>
        {/* Left panel: Tabs + content */}
        <div>
          {/* Tab bar */}
          <div className="flex items-center gap-1 border-b border-border mb-6">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`relative px-4 py-2.5 text-sm font-medium transition-colors ${
                  activeTab === tab.id
                    ? 'text-primary border-b-2 border-primary -mb-px'
                    : 'text-text-muted hover:text-text'
                }`}
              >
                {tab.label}
              </button>
            ))}
            {/* Toggle viewer button (desktop only) */}
            {hasArtifacts && (
              <button
                onClick={() => setViewerOpen(!viewerOpen)}
                className={`hidden lg:flex items-center gap-1.5 ml-auto px-3 py-2 text-sm font-medium rounded-md transition-colors ${
                  viewerOpen
                    ? 'text-primary bg-primary/5 hover:bg-primary/10'
                    : 'text-text-muted hover:text-text hover:bg-surface-alt'
                }`}
                title={viewerOpen ? 'Hide original file' : 'Show original file'}
              >
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
                </svg>
                {viewerOpen ? 'Hide Original' : 'View Original'}
              </button>
            )}
          </div>

          {/* Tab content */}
          {activeTab === 'summary' && (
            <Card>
              <SummaryTab summary={data.summary} />
            </Card>
          )}

          {activeTab === 'qa' && courseCode && (
            <Card>
              <ScopedQA
                courseCode={courseCode}
                week={data.week}
                onCitationClick={handleCitationClick}
              />
            </Card>
          )}

          {activeTab === 'flashcards' && courseCode && (
            <Card>
              <FlashcardsTab courseCode={courseCode} week={data.week} />
            </Card>
          )}

          {activeTab === 'quiz' && courseCode && (
            <Card>
              <QuizTab courseCode={courseCode} week={data.week} />
            </Card>
          )}

          {/* Artifact list */}
          <div className="mt-6">
            <ArtifactList
              artifacts={data.artifacts}
              selectedArtifactId={selectedArtifactId}
              onSelectArtifact={handleSelectArtifact}
            />
          </div>
        </div>

        {/* Right panel: File viewer (desktop only, togglable) */}
        {hasArtifacts && viewerOpen && (
          <div className="hidden lg:flex lg:flex-col lg:sticky lg:top-4 lg:self-start overflow-hidden" style={{ height: 'calc(100vh - 8rem)' }}>
            <FileViewerToolbar
              artifacts={data.artifacts}
              selectedArtifact={selectedArtifact}
              onSelectArtifact={handleSelectArtifact}
              currentPage={viewerCurrentPage}
              totalPages={viewerTotalPages}
              onGoToPage={handleGoToPage}
            />
            <div className="flex-1 overflow-hidden rounded-b-lg border border-t-0 border-border">
              {selectedArtifact && (
                <FileViewer
                  artifact={selectedArtifact}
                  targetPage={viewerTargetPage}
                  navToken={navToken}
                  onPageChange={setViewerCurrentPage}
                  onTotalPages={setViewerTotalPages}
                />
              )}
            </div>
          </div>
        )}
      </div>

      {/* Mobile viewer modal */}
      <ViewOriginalModal
        open={mobileViewerOpen}
        onClose={() => setMobileViewerOpen(false)}
        artifacts={data.artifacts}
        selectedArtifact={selectedArtifact}
        onSelectArtifact={handleSelectArtifact}
        targetPage={viewerTargetPage}
        navToken={navToken}
        currentPage={viewerCurrentPage}
        totalPages={viewerTotalPages}
        onPageChange={setViewerCurrentPage}
        onTotalPages={setViewerTotalPages}
        onGoToPage={handleGoToPage}
      />
    </div>
  )
}
