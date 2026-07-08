import { Search, ArrowRight, FileText, Layers, MessageSquare, Play, Upload, ClipboardPaste, Moon } from 'lucide-react'
import { SectionLabel } from '../ui'

const results = {
  actions: [
    { icon: Play, label: 'Start study session', hint: 'S' },
    { icon: Upload, label: 'Upload files', hint: 'U' },
    { icon: ClipboardPaste, label: 'Quick capture — paste text or URL', hint: '⌘V' },
    { icon: Moon, label: 'Toggle theme', hint: 'T' },
  ],
  courses: [
    { icon: Layers, label: 'CSIT302 — Cybersecurity', sub: '9 weeks · 142 cards' },
    { icon: Layers, label: 'CSIT302 · Week 9 — Memory Forensics', sub: 'summary · 24 pages' },
  ],
  content: [
    { icon: FileText, label: 'ASLR randomizes stack, heap and library bases…', sub: 'flashcard · CSIT302 wk 7' },
    { icon: FileText, label: 'Memory acquisition: live vs dead-box imaging', sub: 'summary section · CSIT302 wk 9' },
    { icon: MessageSquare, label: 'explain ASLR bypasses', sub: 'chat session · 2h ago' },
  ],
}

export function CommandPalette() {
  return (
    <div className="min-h-full flex items-start justify-center pt-24 pb-12 px-6">
      <div className="w-full max-w-xl">
        {/* the palette */}
        <div className="bg-surface-1 border border-border-strong rounded-xl shadow-2xl shadow-black/20 overflow-hidden">
          <div className="flex items-center gap-3 px-4 py-3.5 border-b border-border">
            <Search size={15} className="text-text-faint" />
            <span className="text-sm text-text">
              asl<span className="animate-pulse text-text-faint">|</span>
            </span>
            <kbd className="ml-auto">esc</kbd>
          </div>

          <div className="max-h-96 overflow-y-auto py-2">
            <div className="px-3">
              <SectionLabel>Actions</SectionLabel>
            </div>
            {results.actions.map((r, i) => (
              <button
                key={r.label}
                className={`w-full flex items-center gap-3 px-4 py-2 text-[13px] cursor-pointer ${
                  i === 0 ? 'bg-surface-2 text-text' : 'text-text-muted hover:bg-surface-2'
                }`}
              >
                <r.icon size={14} className="text-text-faint shrink-0" />
                <span className="truncate">{r.label}</span>
                <kbd className="ml-auto">{r.hint}</kbd>
              </button>
            ))}

            <div className="px-3 mt-3">
              <SectionLabel>Courses & weeks</SectionLabel>
            </div>
            {results.courses.map((r) => (
              <button key={r.label} className="w-full flex items-center gap-3 px-4 py-2 text-[13px] text-text-muted hover:bg-surface-2 cursor-pointer">
                <r.icon size={14} className="text-text-faint shrink-0" />
                <span className="truncate text-text">{r.label}</span>
                <span className="ml-auto text-[11px] text-text-faint shrink-0">{r.sub}</span>
              </button>
            ))}

            <div className="px-3 mt-3">
              <SectionLabel>Content — semantic matches</SectionLabel>
            </div>
            {results.content.map((r) => (
              <button key={r.label} className="w-full flex items-center gap-3 px-4 py-2 text-[13px] text-text-muted hover:bg-surface-2 cursor-pointer">
                <r.icon size={14} className="text-text-faint shrink-0" />
                <span className="truncate">{r.label}</span>
                <span className="ml-auto text-[11px] text-text-faint shrink-0">{r.sub}</span>
              </button>
            ))}
          </div>

          <div className="flex items-center gap-4 px-4 py-2.5 border-t border-border text-[11px] text-text-faint font-mono">
            <span className="flex items-center gap-1.5"><kbd>↑↓</kbd> navigate</span>
            <span className="flex items-center gap-1.5"><kbd>↵</kbd> open</span>
            <span className="flex items-center gap-1.5"><kbd>tab</kbd> filter type</span>
            <span className="ml-auto flex items-center gap-1.5">
              ask this as a question <ArrowRight size={11} /> <kbd>⌘↵</kbd>
            </span>
          </div>
        </div>

        <p className="text-xs text-text-faint mt-6 leading-relaxed max-w-md mx-auto text-center">
          One entry point for everything: navigation, actions, global search across courses, summaries,
          flashcards and chats — plus quick capture. <kbd>⌘K</kbd> anywhere, <kbd>⌘↵</kbd> escalates the query to Ask.
        </p>
      </div>
    </div>
  )
}
