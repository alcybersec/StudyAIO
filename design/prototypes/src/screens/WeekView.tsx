import { useState } from 'react'
import {
  ChevronLeft,
  ChevronRight,
  FileText,
  FolderInput,
  PanelRightClose,
  PanelRightOpen,
  X,
  ZoomIn,
  ZoomOut,
} from 'lucide-react'
import { Badge, Button, Card, EmptyState, ErrorState, FakeSelect, Input, SectionLabel, Skeleton, SkeletonRows } from '../ui'
import { PageShell } from './shared'
import { useSim } from '../lib/sim'
import { flashcards } from '../lib/mock'

type Tab = 'summary' | 'flashcards' | 'quiz'

const TABS: { id: Tab; label: string }[] = [
  { id: 'summary', label: 'Summary' },
  { id: 'flashcards', label: 'Flashcards' },
  { id: 'quiz', label: 'Quiz' },
]

const definitions = [
  { term: 'Volatile memory', def: 'RAM contents lost on power-off — processes, keys, decrypted payloads.' },
  { term: 'Memory image', def: 'Bit-for-bit acquisition of physical RAM taken for offline analysis.' },
  { term: 'KDBG', def: 'Windows kernel debugger block; anchor structure for process enumeration.' },
  { term: 'DKOM', def: 'Direct Kernel Object Manipulation — unlinking structures to hide processes.' },
]

const examTopics = [
  'Order of volatility and why acquisition sequence matters',
  'Process listing cross-views: pslist vs psscan discrepancies',
  'Detecting DKOM-based process hiding in a memory image',
  'Recovering TLS keys and decrypted buffers from RAM',
]

/* ------------------------------------------------------------- Summary tab */

function SummaryContent() {
  return (
    <div className="space-y-5">
      <div>
        <SectionLabel>Key concepts</SectionLabel>
        <ul className="text-[13px] space-y-1.5 list-disc list-inside marker:text-text-faint">
          <li>
            <span className="font-medium">Order of volatility</span> — capture RAM before disk; registers and caches
            decay first.
          </li>
          <li>
            <span className="font-medium">Acquisition tools</span> — WinPmem / LiME produce raw images; minimize
            footprint on the live system.
          </li>
          <li>
            <span className="font-medium">Structured analysis</span> — Volatility walks kernel structures (EPROCESS
            lists, VADs, handle tables) instead of grepping bytes.
          </li>
          <li>
            <span className="font-medium">Anti-forensics</span> — rootkits unlink or overwrite structures; carve with
            pool-tag scanning to find what listing hides.
          </li>
        </ul>
      </div>

      <div>
        <SectionLabel>Definitions</SectionLabel>
        <div className="border border-border rounded-lg overflow-hidden">
          <div className="divide-y divide-border text-[13px]">
            {definitions.map((d) => (
              <div key={d.term} className="flex gap-3 px-3 py-1.5">
                <span className="font-mono text-xs text-peri-fg shrink-0 w-32 pt-0.5">{d.term}</span>
                <span className="text-text-muted">{d.def}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div>
        <SectionLabel>Potential exam topics</SectionLabel>
        <ul className="text-[13px] divide-y divide-border">
          {examTopics.map((t, i) => (
            <li key={i} className="flex items-center gap-2.5 py-1.5">
              <span className="font-mono text-[10px] text-text-faint shrink-0">{String(i + 1).padStart(2, '0')}</span>
              <span>{t}</span>
            </li>
          ))}
        </ul>
      </div>

      <p className="text-[11px] text-text-faint font-mono">
        source: week9_forensics.pdf · summary v2 · generated 2h ago
      </p>
    </div>
  )
}

/* ---------------------------------------------------------- Flashcards tab */

function FlashcardsContent() {
  return (
    <div className="space-y-2.5">
      {flashcards.map((f, i) => (
        <div key={i} className="bg-surface-2 rounded-lg p-3">
          <div className="flex items-start justify-between gap-3">
            <p className="text-[13px] font-medium">{f.front}</p>
            <Badge tone="muted" className="shrink-0">wk {f.week}</Badge>
          </div>
          <p className="text-xs text-text-muted mt-2 leading-relaxed">{f.back}</p>
        </div>
      ))}
      <div className="flex items-center justify-between pt-1">
        <span className="text-[11px] text-text-faint font-mono">14 cards this week · 9 due</span>
        <Button size="sm" kbd="S">Study these</Button>
      </div>
    </div>
  )
}

/* ---------------------------------------------------------------- Quiz tab */

function QuizContent() {
  return (
    <div className="space-y-3">
      <div className="bg-surface-2 rounded-lg p-3">
        <p className="text-[13px] font-medium">
          Which Volatility discrepancy most strongly suggests DKOM process hiding?
        </p>
        <ul className="text-[13px] mt-2.5 space-y-1.5">
          {[
            'pslist shows a process psscan does not',
            'psscan shows a process pslist does not',
            'both plugins agree on the process list',
            'the KDBG signature appears twice',
          ].map((opt, i) => (
            <li
              key={i}
              className={`flex items-center gap-2.5 rounded-md px-2.5 py-1.5 border ${
                i === 1 ? 'border-sage/40 bg-sage-soft text-sage-fg' : 'border-border text-text-muted'
              }`}
            >
              <span className="font-mono text-[10px]">{String.fromCharCode(65 + i)}</span>
              {opt}
            </li>
          ))}
        </ul>
      </div>
      <div className="flex items-center justify-between">
        <span className="text-[11px] text-text-faint font-mono">question 1 of 6 · last attempt 61%</span>
        <Button size="sm" variant="secondary" kbd="Q">Retake quiz</Button>
      </div>
    </div>
  )
}

/* --------------------------------------------------------------- PDF panel */

function PdfViewer() {
  // Static, non-pulsing "text lines" — this is a fake rendered page, not a loading state.
  const lineWidths = ['w-3/4', 'w-full', 'w-full', 'w-5/6', 'w-2/3', 'w-full', 'w-11/12', 'w-1/2', 'w-full', 'w-4/5', 'w-full', 'w-3/5']
  return (
    <div className="bg-surface-0 border border-border rounded-xl overflow-hidden flex flex-col">
      {/* toolbar */}
      <div className="flex items-center gap-2 px-3 py-2 border-b border-border bg-surface-1">
        <FileText size={13} className="text-text-faint shrink-0" />
        <span className="font-mono text-[11px] text-text-muted truncate">week9_forensics.pdf</span>
        <div className="ml-auto flex items-center gap-1.5 shrink-0">
          <Button variant="ghost" size="sm" aria-label="Zoom out" kbd="-">
            <ZoomOut size={13} />
          </Button>
          <span className="font-mono text-[11px] text-text-faint">100%</span>
          <Button variant="ghost" size="sm" aria-label="Zoom in" kbd="+">
            <ZoomIn size={13} />
          </Button>
          <span className="w-px h-4 bg-border mx-1" aria-hidden />
          <Button variant="ghost" size="sm" aria-label="Previous page" kbd="←">
            <ChevronLeft size={13} />
          </Button>
          <Button variant="ghost" size="sm" aria-label="Next page" kbd="→">
            <ChevronRight size={13} />
          </Button>
        </div>
      </div>
      {/* fake page */}
      <div className="flex-1 p-5 flex justify-center overflow-hidden">
        <div className="bg-surface-1 border border-border rounded-md w-full max-w-sm p-6 space-y-2.5" aria-label="Page 3 preview">
          <div className="h-4 w-2/3 bg-surface-2 rounded-sm mb-4" />
          {lineWidths.map((w, i) => (
            <div key={i} className={`h-2 ${w} bg-surface-2 rounded-sm`} />
          ))}
          <div className="h-16 w-full bg-surface-2 rounded-md mt-4" />
        </div>
      </div>
      {/* footer */}
      <div className="flex items-center justify-center px-3 py-1.5 border-t border-border bg-surface-1">
        <span className="font-mono text-[11px] text-text-faint">page 3 / 24</span>
      </div>
    </div>
  )
}

/* ------------------------------------------------------- Reclassify panel */

function ReclassifyPanel({ onClose }: { onClose: () => void }) {
  return (
    <Card className="mb-4 border-peri/30">
      <div className="flex items-start justify-between mb-3">
        <div>
          <p className="text-sm font-semibold flex items-center gap-2">
            <FolderInput size={14} className="text-peri-fg" /> Reclassify this week's material
          </p>
          <p className="text-xs text-text-muted mt-1">
            Applies to <span className="font-mono">week9_forensics.pdf</span> — currently{' '}
            <Badge tone="muted">CSIT302 · Week 9</Badge>
          </p>
        </div>
        <button onClick={onClose} className="text-text-faint hover:text-text-muted cursor-pointer p-1" aria-label="Close">
          <X size={14} />
        </button>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-[1fr_120px_auto] gap-3 items-end max-w-lg">
        <FakeSelect label="Move to course" value="CSCI368 — Network Security" />
        <Input id="rw" label="Week" defaultValue="7" />
        <div className="flex gap-2">
          <Button size="md">Move</Button>
          <Button size="md" variant="ghost" onClick={onClose}>Cancel</Button>
        </div>
      </div>
      <p className="text-[11px] text-text-faint mt-3">
        The summary, flashcards and quiz move with the file. If the destination week already has a summary, it's
        re-generated as a new version merging both sources — nothing is overwritten silently.
      </p>
    </Card>
  )
}

/* ------------------------------------------------------------------ Screen */

export function WeekView() {
  const { sim } = useSim()
  const [tab, setTab] = useState<Tab>('summary')
  const [viewerOpen, setViewerOpen] = useState(true)
  const [reclassifyOpen, setReclassifyOpen] = useState(true)

  const content =
    sim === 'loading' ? (
      <div className="space-y-5">
        <Skeleton className="h-3 w-24" />
        <SkeletonRows rows={4} />
        <Skeleton className="h-3 w-24" />
        <SkeletonRows rows={4} />
      </div>
    ) : sim === 'empty' ? (
      <EmptyState
        title="No summary for this week yet"
        hint="Upload the Week 9 lecture and the pipeline will summarize it automatically."
        action={<Button size="sm">Upload lecture</Button>}
      />
    ) : tab === 'summary' ? (
      <SummaryContent />
    ) : tab === 'flashcards' ? (
      <FlashcardsContent />
    ) : (
      <QuizContent />
    )

  return (
    <PageShell
      title="Week 9 — Memory Forensics"
      subtitle={
        <span className="font-mono">
          <span className="text-text-faint">CSIT302</span>
          <span className="text-text-faint mx-1.5">/</span>
          Week 9
        </span>
      }
      actions={
        <>
          <Button variant="ghost" size="sm" onClick={() => setReclassifyOpen((v) => !v)} aria-pressed={reclassifyOpen}>
            <FolderInput size={13} /> Reclassify
          </Button>
          <Button variant="ghost" size="sm" onClick={() => setViewerOpen((v) => !v)} aria-pressed={viewerOpen}>
            {viewerOpen ? <PanelRightClose size={13} /> : <PanelRightOpen size={13} />}
            {viewerOpen ? 'Hide original' : 'Show original'}
          </Button>
        </>
      }
      wide
    >
      {reclassifyOpen && sim !== 'loading' && <ReclassifyPanel onClose={() => setReclassifyOpen(false)} />}
      <div className={`grid grid-cols-1 gap-4 ${viewerOpen ? 'lg:grid-cols-[1fr_minmax(320px,42%)]' : ''}`}>
        {/* left: tabbed content — its own isolated region */}
        <Card>
          <div className="flex items-center gap-1 border-b border-border -mx-4 px-4 pb-0 mb-4" role="tablist">
            {TABS.map((t) => (
              <button
                key={t.id}
                role="tab"
                aria-selected={tab === t.id}
                onClick={() => setTab(t.id)}
                className={`text-[13px] px-3 py-2 -mb-px border-b-2 transition-colors cursor-pointer ${
                  tab === t.id
                    ? 'border-sage text-text font-medium'
                    : 'border-transparent text-text-muted hover:text-text'
                }`}
              >
                {t.label}
              </button>
            ))}
          </div>
          {content}
        </Card>

        {/* right: PDF viewer — fails alone; summary stays useful */}
        {viewerOpen && (
          <div className="min-h-[420px]">
            {sim === 'loading' ? (
              <Card className="h-full flex flex-col gap-3">
                <Skeleton className="h-6 w-full" />
                <Skeleton className="flex-1 min-h-72 w-full" />
                <Skeleton className="h-3 w-20 mx-auto" />
              </Card>
            ) : sim === 'error' ? (
              <ErrorState
                title="Original PDF couldn't load"
                detail="GET /api/artifacts/a91f/download → 500 Internal Server Error"
                onRetry={() => {}}
              />
            ) : sim === 'empty' ? (
              <Card className="h-full">
                <EmptyState title="No original file" hint="This week has no uploaded artifact to preview." />
              </Card>
            ) : (
              <PdfViewer />
            )}
          </div>
        )}
      </div>

      {sim === 'error' && (
        <p className="text-[11px] text-text-faint mt-4 font-mono">
          ↑ note: only the viewer panel failed — the summary keeps working. Regions fail in isolation.
        </p>
      )}
    </PageShell>
  )
}
