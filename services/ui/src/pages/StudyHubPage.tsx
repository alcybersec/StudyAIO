import { useCallback, useEffect, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import { useSearchParams } from 'react-router-dom'
import * as Tabs from '@radix-ui/react-tabs'
import { Badge, PageHeader } from '../components/ui'
import { SyncChip } from '../components/ui/SyncChip'
import { useTabRouting } from '../hooks/useTabRouting'
import { PlanTab } from '../components/study/PlanTab'
import { FlashcardsStudyTab } from '../components/study/FlashcardsStudyTab'
import { TimedStudyTab } from '../components/study/TimedStudyTab'
import { ExamsTab } from '../components/study/ExamsTab'
import { MasteryTab } from '../components/weakspots/MasteryTab'
import { HistoryTab } from '../components/study/HistoryTab'

const TAB_VALUES = ['plan', 'mastery', 'flashcards', 'timed', 'exams', 'history'] as const
type TabValue = (typeof TAB_VALUES)[number]

const tabLabels: Record<TabValue, string> = {
  plan: 'Plan',
  mastery: 'Mastery',
  flashcards: 'Flashcards',
  timed: 'Timed',
  exams: 'Exams',
  history: 'History',
}

// ?exam=, ?create=, ?course= and ?week= are scoped to the exams tab; switching elsewhere clears it.
const TAB_SCOPED_PARAMS: Record<string, TabValue> = {
  exam: 'exams',
  create: 'exams',
  course: 'exams',
  week: 'exams',
}

export function StudyHubPage() {
  const { t } = useTranslation()
  const tabListRef = useRef<HTMLDivElement>(null)

  const [searchParams, setSearchParams] = useSearchParams()
  const [tabFromUrl, setTab] = useTabRouting(TAB_VALUES, 'plan', 'tab', {
    clearParams: TAB_SCOPED_PARAMS,
  })

  // Deep links like /study?exam=<id> (no tab param) auto-start a flashcard
  // session for that exam — keep honoring them with plan as the new default.
  const activeTab: TabValue =
    !searchParams.get('tab') && searchParams.get('exam') ? 'flashcards' : tabFromUrl

  const selectedExamId = searchParams.get('exam') || null

  const handleTabChange = useCallback(
    (value: string) => setTab(value as TabValue),
    [setTab],
  )

  const handleSelectExam = useCallback(
    (examId: string | null) => {
      const params = new URLSearchParams(searchParams)
      if (examId) {
        params.set('exam', examId)
      } else {
        params.delete('exam')
      }
      setSearchParams(params, { replace: true })
    },
    [searchParams, setSearchParams],
  )

  // Keep the active tab visible when the bar scrolls (narrow phones, deep links).
  useEffect(() => {
    const active = tabListRef.current?.querySelector<HTMLElement>('[data-state="active"]')
    active?.scrollIntoView({ block: 'nearest', inline: 'nearest' })
  }, [activeTab])

  return (
    <div>
      <PageHeader
        title={t('Study')}
        subtitle={t('Plan the week, then work the queue')}
        actions={<SyncChip />}
      />

      <Tabs.Root value={activeTab} onValueChange={handleTabChange}>
        <Tabs.List
          ref={tabListRef}
          className="flex gap-1 border-b border-border mb-6 -mt-2 overflow-x-auto overflow-y-hidden max-w-full [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
        >
          {TAB_VALUES.map((tab) => (
            <Tabs.Trigger
              key={tab}
              value={tab}
              className="shrink-0 whitespace-nowrap px-4 py-2.5 text-sm font-medium text-text-muted transition-colors focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-sage border-b-2 border-transparent hover:text-text data-[state=active]:text-text data-[state=active]:border-sage min-h-[44px]"
            >
              {t(tabLabels[tab])}
              {tab === 'plan' && (
                <span className="ml-1.5 inline-flex align-middle">
                  <Badge variant="success">{t('new')}</Badge>
                </span>
              )}
            </Tabs.Trigger>
          ))}
        </Tabs.List>

        <Tabs.Content value="plan" className="focus:outline-none">
          <PlanTab
            onStartToday={() => setTab('flashcards')}
            onCreateExam={() => setTab('exams')}
          />
        </Tabs.Content>

        <Tabs.Content value="mastery" className="focus:outline-none">
          <MasteryTab />
        </Tabs.Content>

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
