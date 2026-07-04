import { Network, List, Sparkles, BookOpen } from 'lucide-react'
import { Card, Badge, Button, Skeleton, SkeletonRows, EmptyState, ErrorState, SectionLabel, FakeSelect } from '../ui'
import { PageShell } from './shared'
import { useSim } from '../lib/sim'

/* ------------------------------------------------------------- graph data */

type Tone = 'sage' | 'peri' | 'amber'

interface Node {
  id: string
  label: string
  x: number
  y: number
  r: number // radius by importance, 6–14
  tone: Tone
}

const toneVar: Record<Tone, string> = {
  sage: 'var(--t-sage)',
  peri: 'var(--t-peri)',
  amber: 'var(--t-amber)',
}

// Hand-placed layout that *reads* as a settled force simulation.
const nodes: Node[] = [
  { id: 'aslr', label: 'ASLR', x: 300, y: 190, r: 14, tone: 'sage' },
  { id: 'rop', label: 'ROP chains', x: 402, y: 128, r: 11, tone: 'sage' },
  { id: 'memfor', label: 'Memory forensics', x: 178, y: 118, r: 12, tone: 'sage' },
  { id: 'tls', label: 'TLS 1.3', x: 520, y: 268, r: 12, tone: 'peri' },
  { id: 'rootkits', label: 'Rootkits', x: 118, y: 236, r: 10, tone: 'sage' },
  { id: 'pagetables', label: 'Page tables', x: 240, y: 322, r: 8, tone: 'amber' },
  { id: 'heap', label: 'Heap spraying', x: 396, y: 262, r: 8, tone: 'sage' },
  { id: 'volatility', label: 'Volatility', x: 84, y: 128, r: 7, tone: 'sage' },
  { id: 'depnx', label: 'DEP/NX', x: 348, y: 84, r: 9, tone: 'sage' },
  { id: 'canaries', label: 'Stack canaries', x: 232, y: 72, r: 8, tone: 'sage' },
  { id: 'kernmod', label: 'Kernel modules', x: 148, y: 330, r: 7, tone: 'peri' },
  { id: 'hyperv', label: 'Hypervisors', x: 486, y: 96, r: 6, tone: 'peri' },
]

const edges: [string, string][] = [
  ['aslr', 'rop'],
  ['aslr', 'depnx'],
  ['aslr', 'canaries'],
  ['aslr', 'heap'],
  ['aslr', 'memfor'],
  ['rop', 'depnx'],
  ['rop', 'heap'],
  ['memfor', 'volatility'],
  ['memfor', 'rootkits'],
  ['rootkits', 'kernmod'],
  ['rootkits', 'pagetables'],
  ['pagetables', 'kernmod'],
  ['heap', 'tls'],
  ['depnx', 'hyperv'],
  ['tls', 'hyperv'],
]

const byId = (id: string): Node => nodes.find((n) => n.id === id)!

const SELECTED = 'aslr'

/* ---------------------------------------------------------------- canvas */

function GraphCanvas() {
  return (
    <svg viewBox="0 0 640 400" role="img" aria-label="Concept graph — 12 concepts, ASLR selected" className="w-full h-auto block">
      {/* edges */}
      {edges.map(([a, b]) => {
        const na = byId(a)
        const nb = byId(b)
        return (
          <line
            key={`${a}-${b}`}
            x1={na.x}
            y1={na.y}
            x2={nb.x}
            y2={nb.y}
            style={{ stroke: 'var(--t-border-strong)' }}
            strokeWidth={a === SELECTED || b === SELECTED ? 1.5 : 1}
          />
        )
      })}
      {/* nodes */}
      {nodes.map((n) => {
        const selected = n.id === SELECTED
        return (
          <g key={n.id} className="cursor-pointer">
            {selected && (
              <circle cx={n.x} cy={n.y} r={n.r + 5} fill="none" style={{ stroke: toneVar[n.tone] }} strokeWidth={1.5} strokeOpacity={0.55} />
            )}
            <circle cx={n.x} cy={n.y} r={n.r} style={{ fill: toneVar[n.tone] }} fillOpacity={selected ? 1 : 0.8} />
            <text
              x={n.x}
              y={n.y + n.r + (selected ? 16 : 12)}
              textAnchor="middle"
              style={{
                fill: selected ? 'var(--t-text)' : 'var(--t-text-muted)',
                fontFamily: '"JetBrains Mono", ui-monospace, monospace',
                fontSize: selected ? 12 : 10,
                fontWeight: selected ? 600 : 400,
              }}
            >
              {n.label}
            </text>
          </g>
        )
      })}
    </svg>
  )
}

/* ------------------------------------------------------------- side panel */

function ConceptPanel() {
  return (
    <Card dense className="w-72 shrink-0 self-start">
      <SectionLabel>Selected concept</SectionLabel>
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-sm font-semibold">ASLR</h2>
        <Badge tone="sage">CSIT302</Badge>
      </div>
      <p className="text-xs text-text-muted mt-2 leading-relaxed">
        Address Space Layout Randomization randomizes stack, heap, and library base addresses at process start. It forces
        attackers to leak a runtime address before any ROP chain or shellcode redirect can land.
      </p>

      <div className="mt-4">
        <SectionLabel>Related concepts</SectionLabel>
        <div className="flex flex-wrap gap-1.5">
          {['ROP chains', 'DEP/NX', 'Stack canaries', 'Heap spraying'].map((c) => (
            <button
              key={c}
              className="text-[11px] font-medium bg-surface-2 text-text-muted hover:text-text border border-transparent hover:border-border rounded-md px-2 py-0.5 cursor-pointer transition-colors"
            >
              {c}
            </button>
          ))}
        </div>
      </div>

      <div className="mt-4">
        <SectionLabel>Appears in</SectionLabel>
        <ul className="text-xs space-y-1.5">
          {[
            { week: 'Week 7', title: 'Exploit mitigation' },
            { week: 'Week 9', title: 'Memory forensics' },
          ].map((w) => (
            <li key={w.week}>
              <button className="flex items-center gap-2 text-text-muted hover:text-text cursor-pointer transition-colors">
                <BookOpen size={12} className="text-text-faint shrink-0" />
                <span className="underline decoration-border-strong underline-offset-2">{w.week}</span>
                <span className="text-text-faint truncate">· {w.title}</span>
              </button>
            </li>
          ))}
        </ul>
      </div>

      <Button size="sm" className="w-full mt-4">
        <Sparkles size={13} /> Study this
      </Button>
    </Card>
  )
}

/* ---------------------------------------------------------------- screen */

export function Knowledge() {
  const { sim } = useSim()

  return (
    <PageShell
      title="Knowledge"
      subtitle="Every extracted concept, linked. Select a node to scope a session."
      actions={
        <>
          <FakeSelect value="All courses" className="w-40" />
          <div className="flex items-center border border-border rounded-lg overflow-hidden" role="group" aria-label="View">
            <button className="flex items-center gap-1.5 text-xs font-medium px-3 py-2 bg-surface-2 text-text cursor-pointer" aria-pressed>
              <Network size={13} /> Graph
            </button>
            <button className="flex items-center gap-1.5 text-xs font-medium px-3 py-2 text-text-muted hover:text-text hover:bg-surface-2 cursor-pointer transition-colors border-l border-border">
              <List size={13} /> List
            </button>
          </div>
        </>
      }
      wide
    >
      {sim === 'loading' ? (
        <div className="flex gap-4 items-start">
          <Card dense className="flex-1">
            <Skeleton className="w-full h-[380px] rounded-lg" />
          </Card>
          <Card dense className="w-72 shrink-0">
            <Skeleton className="h-4 w-24 mb-3" />
            <SkeletonRows rows={4} />
            <Skeleton className="h-8 w-full mt-4" />
          </Card>
        </div>
      ) : sim === 'empty' ? (
        <Card>
          <EmptyState
            icon={<Network size={28} strokeWidth={1.5} />}
            title="No concepts extracted yet"
            hint="Concepts are mined from your summaries. Process a lecture, then extract its concept graph."
            action={
              <Button size="sm">
                <Sparkles size={13} /> Extract concepts
              </Button>
            }
          />
        </Card>
      ) : (
        <>
          <div className="flex gap-4 items-start">
            {/* canvas region — fails alone; the panel structure stays put */}
            <div className="flex-1 min-w-0">
              {sim === 'error' ? (
                <Card dense>
                  <ErrorState title="Graph couldn't load" detail="GET /api/concepts/graph → 500 Internal Server Error" onRetry={() => {}} />
                </Card>
              ) : (
                <Card dense className="bg-surface-0 overflow-hidden">
                  <GraphCanvas />
                </Card>
              )}
              <p className="font-mono text-[11px] text-text-faint mt-3">
                list view is the keyboard/screen-reader twin — arrows navigate, enter opens
              </p>
            </div>
            <ConceptPanel />
          </div>
        </>
      )}
    </PageShell>
  )
}
