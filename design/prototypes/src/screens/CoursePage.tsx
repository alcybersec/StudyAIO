import { useState } from 'react'
import {
  MoreHorizontal, Pencil, Archive, Trash2, Download, Merge, FileText, AlertTriangle, FolderCog,
} from 'lucide-react'
import { Badge, Button, Card, EmptyState, ErrorState, Input, SectionLabel, SkeletonRows } from '../ui'
import { PageShell } from './shared'
import { useSim } from '../lib/sim'

const weeks = [
  { n: 9, topic: 'Memory Forensics', cards: 14, due: 9, quiz: 61, updated: '2h ago' },
  { n: 8, topic: 'Rootkits & Kernel Security', cards: 18, due: 4, quiz: 74, updated: '3d ago' },
  { n: 7, topic: 'Exploit Mitigation (ASLR, DEP, canaries)', cards: 21, due: 6, quiz: 64, updated: '1w ago' },
  { n: 6, topic: 'Malware Analysis Basics', cards: 16, due: 0, quiz: 82, updated: '2w ago' },
  { n: 5, topic: 'Network Scanning & Enumeration', cards: 19, due: 0, quiz: 91, updated: '3w ago' },
]

function ManageMenu() {
  return (
    <div className="absolute right-0 top-full mt-1.5 w-56 bg-surface-1 border border-border-strong rounded-xl shadow-2xl shadow-black/20 py-1.5 z-10">
      {[
        { icon: Pencil, label: 'Rename course' },
        { icon: Merge, label: 'Merge into another course' },
        { icon: Download, label: 'Export — Markdown / Obsidian' },
        { icon: FileText, label: 'Export deadlines (.ics)' },
        { icon: Archive, label: 'Archive course' },
      ].map((it) => (
        <button key={it.label} className="w-full flex items-center gap-2.5 px-3.5 py-2 text-[13px] text-text-muted hover:bg-surface-2 hover:text-text cursor-pointer">
          <it.icon size={14} className="text-text-faint" /> {it.label}
        </button>
      ))}
      <div className="h-px bg-border my-1.5" />
      <button className="w-full flex items-center gap-2.5 px-3.5 py-2 text-[13px] text-red-fg hover:bg-red-soft cursor-pointer">
        <Trash2 size={14} /> Delete course…
      </button>
    </div>
  )
}

function DeleteConfirm() {
  const [typed, setTyped] = useState('')
  return (
    <div className="bg-surface-1 border border-red/30 rounded-xl shadow-2xl shadow-black/20 max-w-md p-5">
      <div className="flex items-center gap-2.5 mb-3">
        <span className="w-8 h-8 rounded-lg bg-red-soft text-red-fg flex items-center justify-center shrink-0">
          <AlertTriangle size={15} />
        </span>
        <div>
          <p className="text-sm font-semibold">Delete CSIT302 — Cybersecurity?</p>
          <p className="text-[11px] text-text-muted">This can't be undone. Archiving keeps everything recoverable.</p>
        </div>
      </div>
      <ul className="text-xs text-text-muted space-y-1 mb-4 ml-1">
        <li>· 9 weeks of summaries (incl. 3 versions of week 7)</li>
        <li>· 142 flashcards with review history</li>
        <li>· 38 quiz questions · 1 active exam · 4 deadlines</li>
        <li>· 11 uploaded source files stay in storage until purged</li>
      </ul>
      <Input
        id="del-confirm"
        label='Type "CSIT302" to confirm'
        placeholder="CSIT302"
        value={typed}
        onChange={(e) => setTyped(e.target.value)}
      />
      <div className="flex justify-end gap-2 mt-4">
        <Button variant="secondary" size="sm">Cancel</Button>
        <Button variant="secondary" size="sm"><Archive size={12} /> Archive instead</Button>
        <Button variant="danger" size="sm" disabled={typed !== 'CSIT302'}>Delete permanently</Button>
      </div>
    </div>
  )
}

export function CoursePage() {
  const { sim } = useSim()
  const [menuOpen, setMenuOpen] = useState(true)

  return (
    <PageShell
      title="CSIT302 — Cybersecurity"
      subtitle={<span className="font-mono">9 weeks · 142 cards · exam in 9 days · <span className="text-sage-fg">68% ready</span></span>}
      actions={
        <>
          <Button variant="secondary" size="sm">Course ops</Button>
          <Button size="sm" kbd="S">Study this course</Button>
          <div className="relative">
            <Button variant="ghost" size="sm" onClick={() => setMenuOpen((v) => !v)} aria-haspopup="menu" aria-expanded={menuOpen} aria-label="Manage course">
              <MoreHorizontal size={15} />
            </Button>
            {menuOpen && <ManageMenu />}
          </div>
        </>
      }
      wide
    >
      {sim === 'loading' && (
        <Card><SkeletonRows rows={6} /></Card>
      )}
      {sim === 'empty' && (
        <EmptyState
          icon={<FolderCog size={28} strokeWidth={1.5} />}
          title="No weeks yet"
          hint="Upload lectures for this course — weeks are created from classification."
          action={<Button size="sm">Upload lectures</Button>}
        />
      )}
      {sim === 'error' && (
        <ErrorState title="Course content couldn't load" detail="GET /api/courses/CSIT302/weeks → 500" onRetry={() => {}} />
      )}
      {(sim === 'default' || sim === 'offline') && (
        <>
          <Card dense>
            <table className="w-full text-[13px]">
              <thead>
                <tr className="text-left text-[10px] font-mono uppercase tracking-[0.1em] text-text-faint">
                  <th className="font-medium py-1.5 pl-1">Week</th>
                  <th className="font-medium">Topic</th>
                  <th className="font-medium text-right">Cards</th>
                  <th className="font-medium text-right">Due</th>
                  <th className="font-medium text-right">Quiz</th>
                  <th className="font-medium text-right pr-1">Updated</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {weeks.map((w) => (
                  <tr key={w.n} className="hover:bg-surface-2/60 cursor-pointer">
                    <td className="py-2 pl-1 font-mono text-text-faint">{String(w.n).padStart(2, '0')}</td>
                    <td className="font-medium">{w.topic}</td>
                    <td className="text-right text-text-muted">{w.cards}</td>
                    <td className="text-right">
                      {w.due > 0 ? <Badge tone="amber">{w.due} due</Badge> : <span className="text-text-faint">—</span>}
                    </td>
                    <td className={`text-right font-medium ${w.quiz < 70 ? 'text-amber-fg' : 'text-sage-fg'}`}>{w.quiz}%</td>
                    <td className="text-right pr-1 font-mono text-[11px] text-text-faint">{w.updated}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>

          <div className="mt-10">
            <SectionLabel>Danger flow — delete confirmation (opens from Manage menu)</SectionLabel>
            <DeleteConfirm />
          </div>
        </>
      )}
    </PageShell>
  )
}
