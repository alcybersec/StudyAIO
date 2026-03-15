import { PageHeader } from '../components/ui'
import { OverviewCards } from '../components/analytics/OverviewCards'
import { StudyHeatmap } from '../components/analytics/StudyHeatmap'
import { RetentionCurve } from '../components/analytics/RetentionCurve'
import { MasteryBreakdown } from '../components/analytics/MasteryBreakdown'

export function AnalyticsPage() {
  return (
    <div>
      <PageHeader
        title="Analytics"
        subtitle="Study insights and performance trends"
        breadcrumbs={[{ label: 'Dashboard', to: '/' }, { label: 'Analytics' }]}
      />

      <div className="space-y-8">
        <OverviewCards />
        <StudyHeatmap />
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          <RetentionCurve />
          <MasteryBreakdown />
        </div>
      </div>
    </div>
  )
}
