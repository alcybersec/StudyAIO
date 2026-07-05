import { Suspense, lazy } from 'react'
import { useParams } from 'react-router-dom'
import { PageHeader, SkeletonCard } from '../components/ui'
import { SectionRail } from '../components/settings/SectionRail'
import {
  DEFAULT_SECTION,
  isSettingsSection,
  type SettingsSectionId,
} from '../components/settings/sectionRegistry'

const AppearanceSection = lazy(() =>
  import('../components/settings/sections/AppearanceSection').then((m) => ({
    default: m.AppearanceSection,
  })),
)
const AiProvidersSection = lazy(() =>
  import('../components/settings/sections/AiProvidersSection').then((m) => ({
    default: m.AiProvidersSection,
  })),
)
const PipelineSection = lazy(() =>
  import('../components/settings/sections/PipelineSection').then((m) => ({
    default: m.PipelineSection,
  })),
)
const NotificationsSettingsSection = lazy(() =>
  import('../components/settings/sections/NotificationsSettingsSection').then((m) => ({
    default: m.NotificationsSettingsSection,
  })),
)
const CalendarSection = lazy(() =>
  import('../components/settings/sections/CalendarSection').then((m) => ({
    default: m.CalendarSection,
  })),
)
const BillingSettingsSection = lazy(() =>
  import('../components/settings/sections/BillingSettingsSection').then((m) => ({
    default: m.BillingSettingsSection,
  })),
)
const AccountSection = lazy(() =>
  import('../components/settings/sections/AccountSection').then((m) => ({
    default: m.AccountSection,
  })),
)

const SECTION_COMPONENTS: Record<SettingsSectionId, React.LazyExoticComponent<() => React.JSX.Element | null>> = {
  appearance: AppearanceSection,
  ai: AiProvidersSection,
  pipeline: PipelineSection,
  notifications: NotificationsSettingsSection,
  calendar: CalendarSection,
  billing: BillingSettingsSection,
  account: AccountSection,
}

export function SettingsPage() {
  const { section } = useParams<{ section: string }>()
  const active: SettingsSectionId = isSettingsSection(section) ? section : DEFAULT_SECTION
  const ActiveSection = SECTION_COMPONENTS[active]

  return (
    <div>
      <PageHeader
        title="Settings"
        subtitle="Everything about how StudyAIO looks, thinks, and reaches you"
      />
      <div className="flex flex-col md:flex-row gap-4 md:gap-8 items-start">
        <SectionRail active={active} />
        <div className="flex-1 min-w-0 w-full">
          <Suspense fallback={<SkeletonCard />}>
            <ActiveSection />
          </Suspense>
        </div>
      </div>
    </div>
  )
}
