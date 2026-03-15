import { useSearchParams } from 'react-router-dom'
import * as Tabs from '@radix-ui/react-tabs'
import { PageHeader } from '../components/ui'
import { OverviewCards } from '../components/analytics/OverviewCards'
import { StudyHeatmap } from '../components/analytics/StudyHeatmap'
import { RetentionCurve } from '../components/analytics/RetentionCurve'
import { MasteryBreakdown } from '../components/analytics/MasteryBreakdown'

const TABS = ['overview', 'heatmap', 'retention', 'mastery'] as const
type TabValue = (typeof TABS)[number]

export function AnalyticsPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const activeTab = (TABS.includes(searchParams.get('tab') as TabValue)
    ? searchParams.get('tab')
    : 'overview') as TabValue

  const handleTabChange = (value: string) => {
    setSearchParams({ tab: value }, { replace: true })
  }

  return (
    <div>
      <PageHeader
        title="Analytics"
        subtitle="Study insights and performance trends"
        breadcrumbs={[{ label: 'Dashboard', to: '/' }, { label: 'Analytics' }]}
      />

      <Tabs.Root value={activeTab} onValueChange={handleTabChange}>
        <Tabs.List className="flex border-b border-border mb-6 gap-1">
          {TABS.map((tab) => (
            <Tabs.Trigger
              key={tab}
              value={tab}
              className="px-4 py-2.5 text-sm font-medium capitalize whitespace-nowrap transition-colors border-b-2 -mb-px text-text-muted border-transparent hover:text-text data-[state=active]:text-primary data-[state=active]:border-primary min-h-[44px]"
            >
              {tab}
            </Tabs.Trigger>
          ))}
        </Tabs.List>

        <Tabs.Content value="overview" className="focus:outline-none">
          <OverviewCards />
        </Tabs.Content>
        <Tabs.Content value="heatmap" className="focus:outline-none">
          <StudyHeatmap />
        </Tabs.Content>
        <Tabs.Content value="retention" className="focus:outline-none">
          <RetentionCurve />
        </Tabs.Content>
        <Tabs.Content value="mastery" className="focus:outline-none">
          <MasteryBreakdown />
        </Tabs.Content>
      </Tabs.Root>
    </div>
  )
}
