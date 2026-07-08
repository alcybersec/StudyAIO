import { useRef, useState } from 'react'
import {
  Palette,
  Bot,
  Workflow,
  Bell,
  Calendar,
  CreditCard,
  ShieldCheck,
  Terminal,
  Sparkles,
  Globe,
  Server,
  Check,
} from 'lucide-react'
import { Button, Input, Card, Badge, SectionLabel } from '../ui'
import { PageShell, SyncChip } from './shared'

/* ------------------------------------------------------------- section nav */

const SECTIONS = [
  { id: 'appearance', label: 'Appearance', icon: Palette },
  { id: 'ai', label: 'AI Providers', icon: Bot },
  { id: 'pipeline', label: 'Pipeline', icon: Workflow },
  { id: 'notifications', label: 'Notifications', icon: Bell },
  { id: 'calendar', label: 'Calendar', icon: Calendar },
  { id: 'billing', label: 'Billing', icon: CreditCard },
  { id: 'account', label: 'Account & Security', icon: ShieldCheck },
] as const

const ACTIVE_SECTION = 'ai'

function SectionRail() {
  return (
    <nav aria-label="Settings sections" className="w-44 shrink-0">
      <ul className="space-y-0.5">
        {SECTIONS.map(({ id, label, icon: Icon }) => {
          const active = id === ACTIVE_SECTION
          return (
            <li key={id}>
              <button
                aria-current={active ? 'true' : undefined}
                className={`w-full flex items-center gap-2 rounded-md px-2.5 py-1.5 text-[13px] text-left transition-colors cursor-pointer ${
                  active
                    ? 'bg-surface-2 text-text font-medium'
                    : 'text-text-muted hover:text-text hover:bg-surface-2/60'
                }`}
              >
                <Icon size={14} className={active ? 'text-sage-fg' : 'text-text-faint'} aria-hidden />
                {label}
              </button>
            </li>
          )
        })}
      </ul>
    </nav>
  )
}

/* ---------------------------------------------------------- provider cards */

type ProviderId = 'claude' | 'anthropic' | 'openai' | 'ollama'

const PROVIDERS: {
  id: ProviderId
  name: string
  icon: typeof Terminal
  desc: string
  status: string
  statusOk: boolean
}[] = [
  {
    id: 'claude',
    name: 'Claude Code CLI',
    icon: Terminal,
    desc: 'Uses your Max plan via the local CLI — no API key needed.',
    status: 'authenticated · last used 2h ago',
    statusOk: true,
  },
  {
    id: 'anthropic',
    name: 'Anthropic API',
    icon: Sparkles,
    desc: 'Direct API access with your own key. Pay per token.',
    status: 'no key configured',
    statusOk: false,
  },
  {
    id: 'openai',
    name: 'OpenAI',
    icon: Globe,
    desc: 'GPT models for summaries, flashcards and Q&A.',
    status: 'no key configured',
    statusOk: false,
  },
  {
    id: 'ollama',
    name: 'Ollama',
    icon: Server,
    desc: 'Local models — private, free, slower on big lectures.',
    status: 'not reachable at localhost:11434',
    statusOk: false,
  },
]

function ProviderCard({
  provider,
  selected,
  onSelect,
}: {
  provider: (typeof PROVIDERS)[number]
  selected: boolean
  onSelect: () => void
}) {
  const Icon = provider.icon
  return (
    <button
      onClick={onSelect}
      aria-pressed={selected}
      className={`text-left rounded-xl border p-3 transition-colors cursor-pointer ${
        selected
          ? 'border-sage ring-1 ring-sage bg-sage-soft/40'
          : 'border-border bg-surface-1 hover:border-border-strong'
      }`}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="flex items-center gap-2 text-[13px] font-semibold">
          <Icon size={14} className={selected ? 'text-sage-fg' : 'text-text-faint'} aria-hidden />
          {provider.name}
        </span>
        {selected && <Badge tone="sage">active</Badge>}
      </div>
      <p className="text-xs text-text-muted mt-1.5">{provider.desc}</p>
      <p className={`text-[11px] font-mono mt-2 ${provider.statusOk ? 'text-sage-fg' : 'text-text-faint'}`}>
        {provider.status}
      </p>
    </button>
  )
}

/* ------------------------------------------------------- AI Providers form */

function AiProvidersSection() {
  const [selected, setSelected] = useState<ProviderId>('claude')
  const [test, setTest] = useState<'idle' | 'testing' | 'ok'>('idle')
  const timer = useRef<number | undefined>(undefined)

  const runTest = () => {
    setTest('testing')
    window.clearTimeout(timer.current)
    timer.current = window.setTimeout(() => setTest('ok'), 1200)
  }

  return (
    <div className="flex-1 min-w-0">
      <SectionLabel>AI Providers</SectionLabel>
      <p className="text-xs text-text-muted mb-4 max-w-lg">
        One provider handles everything — summaries, flashcards, Q&amp;A. Switch anytime; nothing
        already generated is lost.
      </p>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
        {PROVIDERS.map((p) => (
          <ProviderCard key={p.id} provider={p} selected={selected === p.id} onSelect={() => setSelected(p.id)} />
        ))}
      </div>

      {/* form for the selected provider */}
      <Card className="mt-5">
        <div className="text-[13px] font-semibold mb-4">Claude Code CLI configuration</div>

        <div className="space-y-4 max-w-md">
          {/* per-field save feedback demo */}
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label htmlFor="model" className="text-xs font-medium text-text-muted">
                Model
              </label>
              <span className="inline-flex items-center gap-1 text-sage-fg text-[11px]" role="status">
                <Check size={11} aria-hidden /> saved
              </span>
            </div>
            <Input id="model" defaultValue="claude-sonnet-4-6" className="font-mono" />
          </div>

          <Input
            id="api-key"
            label="API key (optional — overrides CLI auth)"
            type="password"
            placeholder="sk-ant-…"
          />

          {/* RHF + zod field-error demo: aria-describedby wiring lives in the Input primitive */}
          <Input
            id="api-key-invalid"
            label="API key — validation error demo"
            type="password"
            defaultValue="sk-live-0f3a9c"
            error="Key must start with sk-ant-"
          />

          <div className="flex items-center gap-3 pt-1">
            <Button variant="secondary" size="sm" loading={test === 'testing'} onClick={runTest}>
              {test === 'testing' ? 'Testing…' : 'Test connection'}
            </Button>
            {test === 'ok' && (
              <span className="text-xs text-sage-fg" role="status">
                ✓ Claude responded in 1.2s
              </span>
            )}
          </div>
        </div>
      </Card>

      {/* section save bar */}
      <div className="flex items-center justify-between mt-4 pt-3 border-t border-border">
        <span className="text-xs text-text-faint">Changes save automatically</span>
        <SyncChip count={1} />
      </div>
    </div>
  )
}

/* ------------------------------------------------------------------ screen */

export function Settings() {
  return (
    <PageShell title="Settings" subtitle="Everything about how StudyAIO looks, thinks, and reaches you" wide>
      <div className="flex gap-8 items-start">
        <SectionRail />
        <AiProvidersSection />
      </div>
    </PageShell>
  )
}
