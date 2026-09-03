import {
  Bell,
  Bot,
  Calendar,
  CreditCard,
  DatabaseZap,
  Palette,
  ShieldCheck,
  Workflow,
  type LucideIcon,
} from 'lucide-react'

export const SETTINGS_SECTIONS = [
  { id: 'appearance', label: 'Appearance', icon: Palette },
  { id: 'ai', label: 'AI Providers', icon: Bot },
  { id: 'pipeline', label: 'Pipeline', icon: Workflow },
  { id: 'notifications', label: 'Notifications', icon: Bell },
  { id: 'calendar', label: 'Calendar', icon: Calendar },
  { id: 'billing', label: 'Billing', icon: CreditCard },
  { id: 'account', label: 'Account & Security', icon: ShieldCheck },
  { id: 'privacy', label: 'Data & Privacy', icon: DatabaseZap },
] as const satisfies readonly { id: string; label: string; icon: LucideIcon }[]

export type SettingsSectionId = (typeof SETTINGS_SECTIONS)[number]['id']

export const DEFAULT_SECTION: SettingsSectionId = 'appearance'

export function isSettingsSection(value: string | undefined): value is SettingsSectionId {
  return SETTINGS_SECTIONS.some((s) => s.id === value)
}
