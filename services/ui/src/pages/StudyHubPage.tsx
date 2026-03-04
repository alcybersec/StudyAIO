import { useCallback } from 'react'
import { useSearchParams } from 'react-router-dom'
import * as Tabs from '@radix-ui/react-tabs'
import { PageHeader } from '../components/ui'
import { FlashcardsStudyTab } from '../components/study/FlashcardsStudyTab'
import { TimedStudyTab } from '../components/study/TimedStudyTab'
import { ExamsTab } from '../components/study/ExamsTab'
import { HistoryTab } from '../components/study/HistoryTab'

const TAB_VALUES = ['flashcards', 'timed', 'exams', 'history'] as const
type TabValue = (typeof TAB_VALUES)[number]

const tabLabels: Record<TabValue, string> = {
  flashcards: 'Flashcards',
  timed: 'Timed',
  exams: 'Exams',
  history: 'History',
}

export function StudyHubPage() {
  const [searchParams, setSearchParams] = useSearchParams()

  const activeTab = (TAB_VALUES.includes(searchParams.get('tab') as TabValue)
    ? searchParams.get('tab')
    : 'flashcards') as TabValue

  const selectedExamId = searchParams.get('exam') || null

  const handleTabChange = useCallback((value: string) => {
    const params = new URLSearchParams(searchParams)
    params.set('tab', value)
    // Clear exam selection when switching away from exams tab
    if (value !== 'exams') params.delete('exam')
    setSearchParams(params, { replace: true })
  }, [searchParams, setSearchParams])

  const handleSelectExam = useCallback((examId: string | null) => {
    const params = new URLSearchParams(searchParams)
    if (examId) {
      params.set('exam', examId)
    } else {
      params.delete('exam')
    }
    setSearchParams(params, { replace: true })
  }, [searchParams, setSearchParams])

  return (
    <div>
      <PageHeader
        title="Study"
        subtitle="Flashcards, timed sessions, exams, and progress tracking"
      />

      <Tabs.Root value={activeTab} onValueChange={handleTabChange}>
        <Tabs.List className="flex gap-1 border-b border-border mb-6 -mt-2">
          {TAB_VALUES.map((tab) => (
            <Tabs.Trigger
              key={tab}
              value={tab}
              className="px-4 py-2.5 text-sm font-medium text-text-muted transition-colors border-b-2 border-transparent hover:text-text data-[state=active]:text-primary data-[state=active]:border-primary min-h-[44px]"
            >
              {tabLabels[tab]}
            </Tabs.Trigger>
          ))}
        </Tabs.List>

        <Tabs.Content value="flashcards" className="focus:outline-none">
          <FlashcardsStudyTab />
        </Tabs.Content>

        <Tabs.Content value="timed" className="focus:outline-none">
          <TimedStudyTab />
        </Tabs.Content>

        <Tabs.Content value="exams" className="focus:outline-none">
          <ExamsTab selectedExamId={selectedExamId} onSelectExam={handleSelectExam} />
        </Tabs.Content>

        <Tabs.Content value="history" className="focus:outline-none">
          <HistoryTab />
        </Tabs.Content>
      </Tabs.Root>
    </div>
  )
}
