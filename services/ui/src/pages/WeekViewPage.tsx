import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useWeekDetail } from '../hooks/useApi'
import { LoadingSpinner, EmptyState, PageHeader, Card } from '../components/ui'
import { SummaryTab } from '../components/week/SummaryTab'
import { ArtifactList } from '../components/week/ArtifactList'
import { ScopedQA } from '../components/qa/ScopedQA'
import { FlashcardsTab } from '../components/week/FlashcardsTab'
import { QuizTab } from '../components/week/QuizTab'

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
  const { data, isLoading, error } = useWeekDetail(courseCode ?? '', week)
  const [activeTab, setActiveTab] = useState<Tab>('summary')

  if (isLoading) return <LoadingSpinner label="Loading week..." />
  if (error) return <EmptyState icon="!" title="Failed to load week" />
  if (!data) return <EmptyState icon="?" title="Week not found" />

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

      {/* Tab bar */}
      <div className="flex items-center gap-1 border-b border-gray-200 mb-6">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`relative px-4 py-2.5 text-sm font-medium transition-colors ${
              activeTab === tab.id
                ? 'text-primary border-b-2 border-primary -mb-px'
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {activeTab === 'summary' && (
        <Card>
          <SummaryTab summary={data.summary} />
        </Card>
      )}

      {activeTab === 'qa' && courseCode && (
        <Card>
          <ScopedQA courseCode={courseCode} week={data.week} />
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

      {/* Artifact list always visible below */}
      <div className="mt-6">
        <ArtifactList artifacts={data.artifacts} />
      </div>
    </div>
  )
}
