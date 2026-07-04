import { useEffect, useMemo, useRef, useState, type KeyboardEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import * as Dialog from '@radix-ui/react-dialog'
import {
  ClipboardPaste,
  Layers,
  Moon,
  Play,
  Search,
  Upload,
  type LucideIcon,
} from 'lucide-react'
import { useCourses } from '../hooks/useApi'
import { useTheme } from '../hooks/useTheme'
import { onCommandPaletteOpen } from '../lib/commandPalette'
import { Kbd } from './ui/Kbd'
import { Modal } from './ui/Modal'

/** Flips on when the E1 global-search endpoint lands. */
const searchAvailable = false

interface PaletteItem {
  id: string
  section: string
  label: string
  sub?: string
  hint?: string
  icon: LucideIcon
  run: () => void
}

export function CommandPalette() {
  const [open, setOpen] = useState(false)
  const [captureOpen, setCaptureOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [activeIndex, setActiveIndex] = useState(0)
  const listRef = useRef<HTMLDivElement>(null)
  const navigate = useNavigate()
  const { toggle: toggleTheme } = useTheme()
  const { data: courses } = useCourses()

  // Sidebar affordance + ⌘K both open through the shared event channel.
  // Transient state resets on open (not in an effect — lint: set-state-in-effect).
  useEffect(
    () =>
      onCommandPaletteOpen(() => {
        setQuery('')
        setActiveIndex(0)
        setOpen(true)
      }),
    [],
  )

  const items = useMemo<PaletteItem[]>(() => {
    const actions: PaletteItem[] = [
      {
        id: 'action-study',
        section: 'Actions',
        label: 'Start study session',
        hint: 'S',
        icon: Play,
        run: () => navigate('/study'),
      },
      {
        id: 'action-upload',
        section: 'Actions',
        label: 'Upload files',
        hint: 'U',
        icon: Upload,
        run: () => navigate('/upload'),
      },
      {
        id: 'action-capture',
        section: 'Actions',
        label: 'Quick capture — paste text or URL',
        icon: ClipboardPaste,
        run: () => setCaptureOpen(true),
      },
      {
        id: 'action-theme',
        section: 'Actions',
        label: 'Toggle theme',
        icon: Moon,
        run: () => toggleTheme(),
      },
    ]
    const navigateItems: PaletteItem[] = (courses ?? []).map((course) => ({
      id: `course-${course.code}`,
      section: 'Navigate',
      label: course.code,
      sub: `${course.name} · ${course.weeks_covered}w`,
      icon: Layers,
      run: () => navigate(`/courses/${course.code}`),
    }))
    // "Content" section (global search results) stays hidden until the
    // E1 search endpoint exists — flip `searchAvailable` and append the
    // grouped results here when it lands.
    const contentItems: PaletteItem[] = searchAvailable ? [] : []
    return [...actions, ...navigateItems, ...contentItems]
  }, [courses, navigate, toggleTheme])

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) return items
    return items.filter(
      (item) => item.label.toLowerCase().includes(q) || item.sub?.toLowerCase().includes(q),
    )
  }, [items, query])

  const clampedIndex = Math.min(activeIndex, Math.max(filtered.length - 1, 0))

  const runItem = (item: PaletteItem | undefined) => {
    if (!item) return
    setOpen(false)
    item.run()
  }

  const handleKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'ArrowDown') {
      event.preventDefault()
      setActiveIndex((i) => Math.min(i + 1, filtered.length - 1))
    } else if (event.key === 'ArrowUp') {
      event.preventDefault()
      setActiveIndex((i) => Math.max(i - 1, 0))
    } else if (event.key === 'Enter') {
      event.preventDefault()
      runItem(filtered[clampedIndex])
    }
  }

  // Group for section labels while keeping a flat index for keyboard nav.
  let lastSection = ''

  return (
    <>
      <Dialog.Root open={open} onOpenChange={setOpen}>
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 bg-black/50 z-50" />
          <Dialog.Content
            className="fixed left-1/2 top-24 -translate-x-1/2 z-50 w-[calc(100vw-2rem)] max-w-xl bg-surface-1 border border-border-strong rounded-xl shadow-2xl shadow-black/20 overflow-hidden focus:outline-none"
            aria-describedby={undefined}
          >
            <Dialog.Title className="sr-only">Command palette</Dialog.Title>
            <div className="flex items-center gap-3 px-4 py-3.5 border-b border-border">
              <Search size={15} className="text-text-faint shrink-0" aria-hidden />
              <input
                role="combobox"
                aria-label="Search commands and destinations"
                aria-expanded="true"
                aria-controls="command-palette-list"
                aria-activedescendant={filtered[clampedIndex]?.id}
                autoFocus
                value={query}
                onChange={(e) => {
                  setQuery(e.target.value)
                  setActiveIndex(0)
                }}
                onKeyDown={handleKeyDown}
                placeholder="Search or jump to…"
                className="flex-1 bg-transparent text-sm text-text placeholder:text-text-faint focus:outline-none"
              />
              <Kbd>esc</Kbd>
            </div>

            <div
              id="command-palette-list"
              role="listbox"
              aria-label="Results"
              ref={listRef}
              className="max-h-96 overflow-y-auto py-2"
            >
              {filtered.length === 0 && (
                <p className="px-4 py-6 text-center text-sm text-text-muted">No matches.</p>
              )}
              {filtered.map((item, index) => {
                const showSection = item.section !== lastSection
                lastSection = item.section
                const active = index === clampedIndex
                return (
                  <div key={item.id}>
                    {showSection && (
                      <div className="px-4 pt-2 pb-1 text-[10px] font-mono uppercase tracking-[0.12em] text-text-faint">
                        {item.section}
                      </div>
                    )}
                    <button
                      type="button"
                      id={item.id}
                      role="option"
                      aria-selected={active}
                      onClick={() => runItem(item)}
                      onMouseMove={() => setActiveIndex(index)}
                      className={`w-full flex items-center gap-3 px-4 py-2 text-[13px] cursor-pointer text-left ${
                        active ? 'bg-surface-2 text-text' : 'text-text-muted hover:bg-surface-2'
                      }`}
                    >
                      <item.icon size={14} className="text-text-faint shrink-0" aria-hidden />
                      <span className="truncate">{item.label}</span>
                      {item.sub && (
                        <span className="ml-auto text-[11px] text-text-faint shrink-0">{item.sub}</span>
                      )}
                      {item.hint && !item.sub && <Kbd className="ml-auto">{item.hint}</Kbd>}
                    </button>
                  </div>
                )
              })}
            </div>

            <div className="flex items-center gap-4 px-4 py-2.5 border-t border-border text-[11px] text-text-faint font-mono">
              <span className="flex items-center gap-1.5">
                <Kbd>↑↓</Kbd> navigate
              </span>
              <span className="flex items-center gap-1.5">
                <Kbd>↵</Kbd> open
              </span>
              <span className="ml-auto flex items-center gap-1.5">
                <Kbd>esc</Kbd> close
              </span>
            </div>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>

      {/* Quick capture placeholder — E4 replaces this with the real capture modal */}
      <Modal
        open={captureOpen}
        onOpenChange={setCaptureOpen}
        title="Quick capture"
        description="Paste text or a URL straight into the pipeline."
      >
        <p className="text-sm text-text-muted">
          Coming soon — quick capture lands with the pipeline update.
        </p>
      </Modal>
    </>
  )
}
