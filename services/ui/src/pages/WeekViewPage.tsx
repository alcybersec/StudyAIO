import { useCallback, useRef, useState } from 'react'
import { useParams, useSearchParams } from 'react-router-dom'
import { Eye, FolderInput, PanelRightClose, PanelRightOpen } from 'lucide-react'
import { useWeekDetail } from '../hooks/useApi'
import { Button, Card, EmptyState, ErrorState, PageHeader, Skeleton, SkeletonText } from '../components/ui'
import { useTabRouting } from '../hooks/useTabRouting'
import { SummaryTab } from '../components/week/SummaryTab'
import { ArtifactList } from '../components/week/ArtifactList'
import { ReclassifyPanel } from '../components/week/ReclassifyPanel'
import { ScopedQA } from '../components/qa/ScopedQA'
import { FlashcardsTab } from '../components/week/FlashcardsTab'
import { QuizTab } from '../components/week/QuizTab'
import { FileViewerContainer, type ViewerHandle, type ViewerStateSnapshot } from '../components/viewer'
import { parseViewerParams } from '../components/viewer/viewerReducer'

const TABS = ['summary', 'qa', 'flashcards', 'quiz'] as const
type Tab = (typeof TABS)[number]

const TAB_LABELS: Record<Tab, string> = {
  summary: 'Summary',
  qa: 'Q&A',
  flashcards: 'Flashcards',
  quiz: 'Quiz',
}

function WeekViewSkeleton() {
  return (
    <div>
      <Skeleton className="h-4 w-48 mb-3" />
      <Skeleton className="h-8 w-64 mb-6" />
      <div className="grid grid-cols-1 lg:grid-cols-[minmax(400px,1.2fr)_minmax(300px,1fr)] gap-6">
        <Card>
          <Skeleton className="h-4 w-24 mb-4" />
          <SkeletonText lines={6} />
        </Card>
        <Card className="hidden lg:flex flex-col gap-3">
          <Skeleton className="h-6 w-full" />
          <Skeleton className="flex-1 min-h-72 w-full" />
          <Skeleton className="h-3 w-20 mx-auto" />
        </Card>
      </div>
    </div>
  )
}

export function WeekViewPage() {
  const { courseCode, weekNumber } = useParams<{ courseCode: string; weekNumber: string }>()
  const week = Number(weekNumber)
  const { data, isLoading, error, refetch } = useWeekDetail(courseCode ?? '', week)

  const [activeTab, setActiveTab] = useTabRouting(TABS, 'summary')
  const [reclassifyOpen, setReclassifyOpen] = useState(false)

  // Deep-link (?artifact=&page=) is read once; afterwards the URL mirrors viewer state.
  const [searchParams, setSearchParams] = useSearchParams()
  const [initialViewer] = useState(() => parseViewerParams(searchParams))

  const viewerRef = useRef<ViewerHandle>(null)
  const [viewer, setViewer] = useState<ViewerStateSnapshot | null>(null)

  const handleViewerChange = useCallback(
    (snapshot: ViewerStateSnapshot) => {
      setViewer(snapshot)
      setSearchParams(
        (prev) => {
          const next = new URLSearchParams(prev)
          if (snapshot.open && snapshot.artifactId) {
            next.set('artifact', snapshot.artifactId)
            next.set('page', String(snapshot.page))
          } else {
            next.delete('artifact')
            next.delete('page')
          }
          return next
        },
        { replace: true },
      )
    },
    [setSearchParams],
  )

  const handleCitationClick = useCallback((artifactId: string, page: number) => {
    viewerRef.current?.openAt(artifactId, page)
  }, [])

  if (isLoading) return <WeekViewSkeleton />
  if (error) {
    return (
      <ErrorState
        title="This week couldn't load"
        detail={error instanceof Error ? error.message : undefined}
        onRetry={() => refetch()}
      />
    )
  }
  if (!data) return <EmptyState icon="?" title="Week not found" />

  const hasArtifacts = data.artifacts.length > 0
  const viewerOpen = viewer?.open ?? false
  const reclassifyArtifact = hasArtifacts
    ? (data.artifacts.find((a) => a.id === viewer?.artifactId) ?? data.artifacts[0])
    : null

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
        actions={
          hasArtifacts ? (
            <>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setReclassifyOpen((v) => !v)}
                aria-pressed={reclassifyOpen}
              >
                <FolderInput size={13} aria-hidden /> Reclassify
              </Button>
              <Button
                variant="ghost"
                size="sm"
                className="hidden lg:inline-flex"
                onClick={() => viewerRef.current?.toggleOpen()}
                aria-pressed={viewerOpen}
              >
                {viewerOpen ? (
                  <PanelRightClose size={13} aria-hidden />
                ) : (
                  <PanelRightOpen size={13} aria-hidden />
                )}
                {viewerOpen ? 'Hide original' : 'Show original'}
              </Button>
              <Button
                variant="ghost"
                size="sm"
                className="lg:hidden"
                onClick={() => viewerRef.current?.openMobile()}
              >
                <Eye size={13} aria-hidden /> View original
              </Button>
            </>
          ) : undefined
        }
      />

      {reclassifyOpen && reclassifyArtifact && courseCode && (
        <ReclassifyPanel
          artifact={reclassifyArtifact}
          courseCode={courseCode}
          week={data.week}
          onClose={() => setReclassifyOpen(false)}
        />
      )}

      {/* Split-panel layout: tabbed content left, original file right (desktop) */}
      <div
        className={`grid grid-cols-1 gap-6 ${
          hasArtifacts && viewerOpen ? 'lg:grid-cols-[minmax(400px,1.2fr)_minmax(300px,1fr)]' : ''
        }`}
      >
        {/* Left region: tabs — fails in isolation from the viewer */}
        <div>
          <div className="flex items-center gap-1 border-b border-border mb-6" role="tablist">
            {TABS.map((tab) => (
              <button
                key={tab}
                role="tab"
                aria-selected={activeTab === tab}
                onClick={() => setActiveTab(tab)}
                className={`px-3 py-2 -mb-px text-sm border-b-2 transition-colors cursor-pointer ${
                  activeTab === tab
                    ? 'border-sage text-text font-medium'
                    : 'border-transparent text-text-muted hover:text-text'
                }`}
              >
                {TAB_LABELS[tab]}
              </button>
            ))}
          </div>

          {activeTab === 'summary' && (
            <Card>
              <SummaryTab summary={data.summary} />
            </Card>
          )}

          {activeTab === 'qa' && courseCode && (
            <Card>
              <ScopedQA courseCode={courseCode} week={data.week} onCitationClick={handleCitationClick} />
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

          <div className="mt-6">
            <ArtifactList
              artifacts={data.artifacts}
              selectedArtifactId={viewer?.artifactId}
              onSelectArtifact={(id) => viewerRef.current?.openAt(id, 1)}
            />
          </div>
        </div>

        {/* Right region: original-file viewer — its failure never touches the tabs */}
        {hasArtifacts && (
          <FileViewerContainer
            artifacts={data.artifacts}
            initialArtifactId={initialViewer.artifactId}
            initialPage={initialViewer.page}
            initialOpen={initialViewer.artifactId !== null}
            onStateChange={handleViewerChange}
            handleRef={viewerRef}
          />
        )}
      </div>
    </div>
  )
}
