import { useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { useLocation } from 'react-router-dom'
import { PageHeader } from '../components/ui'
import { OverviewCards } from '../components/analytics/OverviewCards'
import { StudyHeatmap } from '../components/analytics/StudyHeatmap'
import { RetentionCurve } from '../components/analytics/RetentionCurve'
import { MasteryBreakdown } from '../components/analytics/MasteryBreakdown'
import { ReadinessDrilldown } from '../components/analytics/ReadinessDrilldown'

export function AnalyticsPage() {
  const { t } = useTranslation()

  const { hash } = useLocation()

  // Support deep links like /analytics#readiness (dashboard "why?" links).
  useEffect(() => {
    if (!hash) return
    const el = document.getElementById(hash.slice(1))
    el?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }, [hash])

  return (
    <div>
      <PageHeader
        title={t('Analytics')}
        subtitle={t("What you've studied, how well it stuck, and where the exam risk lives.")}
        breadcrumbs={[{ label: t('Dashboard'), to: '/' }, { label: t('Analytics') }]}
      />

      <div className="space-y-4">
        <OverviewCards />
        <StudyHeatmap />
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <RetentionCurve />
          <MasteryBreakdown />
        </div>
        <section id="readiness" aria-label={t('Exam readiness')} className="scroll-mt-20">
          <ReadinessDrilldown />
        </section>
      </div>
    </div>
  )
}
