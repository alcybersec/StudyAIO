import { Trash2, Upload } from 'lucide-react'
import { Button, Input, Badge, Card, Skeleton, SectionLabel, FakeSelect } from '../ui'

const swatches = [
  ['surface-0', 'bg-surface-0 border border-border'],
  ['surface-1', 'bg-surface-1 border border-border'],
  ['surface-2', 'bg-surface-2'],
  ['sage', 'bg-sage'],
  ['amber', 'bg-amber'],
  ['red', 'bg-red'],
  ['peri', 'bg-peri'],
]

export function Foundations() {
  return (
    <div className="max-w-4xl mx-auto px-6 py-8 space-y-10">
      <div>
        <h1 className="text-xl font-bold tracking-tight mb-1">Foundations</h1>
        <p className="text-xs text-text-muted">Nordic Calm, dark-anchored · quiet chrome, dense content · toggle the theme (top right) to check parity</p>
      </div>

      <section>
        <SectionLabel>Color tokens — semantic, both modes from one set</SectionLabel>
        <div className="flex flex-wrap gap-3">
          {swatches.map(([name, cls]) => (
            <div key={name} className="text-center">
              <div className={`w-16 h-12 rounded-lg ${cls}`} />
              <div className="text-[10px] font-mono text-text-faint mt-1.5">{name}</div>
            </div>
          ))}
        </div>
        <div className="flex gap-2 mt-3">
          <Badge tone="sage">sage-soft / fg</Badge>
          <Badge tone="amber">amber-soft / fg</Badge>
          <Badge tone="red">red-soft / fg</Badge>
          <Badge tone="peri">peri-soft / fg</Badge>
          <Badge tone="muted">muted</Badge>
        </div>
      </section>

      <section>
        <SectionLabel>Type — Inter for UI, JetBrains Mono for data &amp; keys</SectionLabel>
        <Card className="space-y-3">
          <p className="text-xl font-bold tracking-tight">Page title — 20/bold/tight</p>
          <p className="text-sm font-semibold">Section heading — 14/semibold</p>
          <p className="text-sm">Body — 14/regular. Summaries and answers read at a comfortable measure.</p>
          <p className="text-[13px] text-text-muted">Dense row text — 13, muted. Tables, lists, inbox rows.</p>
          <p className="text-xs text-text-faint">Caption — 12, faint.</p>
          <p className="font-mono text-[11px] text-text-muted">mono · file names, timings, counts, keybinds — the power-tool voice</p>
        </Card>
      </section>

      <section>
        <SectionLabel>Buttons — 4 variants × 3 sizes + states</SectionLabel>
        <Card className="space-y-4">
          <div className="flex flex-wrap items-center gap-2.5">
            <Button size="lg">Start session</Button>
            <Button>Primary</Button>
            <Button variant="secondary">Secondary</Button>
            <Button variant="ghost">Ghost</Button>
            <Button variant="danger"><Trash2 size={13} /> Delete</Button>
            <Button size="sm">Small</Button>
          </div>
          <div className="flex flex-wrap items-center gap-2.5">
            <Button loading>Saving…</Button>
            <Button disabled>Disabled</Button>
            <Button variant="secondary" kbd="⌘K">With keybind</Button>
            <Button variant="secondary"><Upload size={13} /> With icon</Button>
          </div>
          <p className="text-[11px] text-text-faint">Focus with the keyboard (tab) — visible periwinkle ring; mouse clicks never show it.</p>
        </Card>
      </section>

      <section>
        <SectionLabel>Form controls — RHF + zod pattern, errors linked via aria-describedby</SectionLabel>
        <Card className="grid grid-cols-2 gap-4 max-w-xl">
          <Input id="f1" label="Course code" placeholder="CSIT302" />
          <Input id="f2" label="Week" defaultValue="14" error="Week must be between 1 and 13" />
          <FakeSelect label="AI provider" value="Claude Code CLI" />
          <Input id="f3" label="API key" type="password" defaultValue="secret" />
        </Card>
      </section>

      <section>
        <SectionLabel>Loading — skeletons mirror the layout, never spinners-in-space</SectionLabel>
        <div className="grid grid-cols-3 gap-3 max-w-xl">
          <Card dense>
            <Skeleton className="h-3 w-12 mb-3" />
            <Skeleton className="h-7 w-20" />
          </Card>
          <Card dense className="col-span-2">
            <Skeleton className="h-3 w-24 mb-3" />
            <div className="space-y-2">
              <Skeleton className="h-3.5 w-full" />
              <Skeleton className="h-3.5 w-3/4" />
              <Skeleton className="h-3.5 w-5/6" />
            </div>
          </Card>
        </div>
      </section>
    </div>
  )
}
