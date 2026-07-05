import { useEffect, useMemo, useRef, useState, type KeyboardEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import * as Dialog from '@radix-ui/react-dialog'
import {
  ArrowRight,
  ClipboardPaste,
  Layers,
  Moon,
  Play,
  Search,
  Upload,
  type LucideIcon,
} from 'lucide-react'
import { searchApi } from '../api/search'
import { useCourses } from '../hooks/useApi'
import { useDebouncedValue } from '../hooks/useDebouncedValue'
import { useTheme } from '../hooks/useTheme'
import { isSearchAvailable, onCommandPaletteOpen } from '../lib/commandPalette'
import {
  searchResultHref,
  searchResultIcon,
  searchResultSection,
  searchResultSub,
} from '../lib/searchResults'
import { Kbd } from './ui/Kbd'
import { QuickCaptureModal } from './QuickCaptureModal'
import { Skeleton } from './ui/Skeleton'

const SEARCH_MIN_CHARS = 2
const SEARCH_DEBOUNCE_MS = 200

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

  // Global search (E1): debounced, only from 2 characters.
  const searchEnabled = isSearchAvailable()
  const trimmedQuery = query.trim()
  const debouncedQuery = useDebouncedValue(trimmedQuery, SEARCH_DEBOUNCE_MS)
  const searchActive = searchEnabled && debouncedQuery.length >= SEARCH_MIN_CHARS
  const search = useQuery({
    queryKey: ['globalSearch', debouncedQuery],
    queryFn: () => searchApi.search(debouncedQuery),
    enabled: open && searchActive,
    staleTime: 30_000,
  })
  const searchPending =
    searchEnabled &&
    trimmedQuery.length >= SEARCH_MIN_CHARS &&
    (debouncedQuery !== trimmedQuery || search.isLoading)

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
        hint: '⌘V',
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
    return [...actions, ...navigateItems]
  }, [courses, navigate, toggleTheme])

  // Content section (E1): server-filtered search results, grouped by kind.
  const searchItems = useMemo<PaletteItem[]>(() => {
    if (!searchActive) return []
    return (search.data?.results ?? []).flatMap((result, index) => {
      const href = searchResultHref(result)
      if (!href) return []
      return [
        {
          id: `search-${result.kind}-${index}`,
          section: searchResultSection(result.kind),
          label: result.title,
          sub: searchResultSub(result),
          icon: searchResultIcon(result.kind),
          run: () => navigate(href),
        },
      ]
    })
  }, [searchActive, search.data, navigate])

  const filtered = useMemo(() => {
    const q = trimmedQuery.toLowerCase()
    const staticFiltered = q
      ? items.filter(
          (item) => item.label.toLowerCase().includes(q) || item.sub?.toLowerCase().includes(q),
        )
      : items
    return [...staticFiltered, ...searchItems]
  }, [items, searchItems, trimmedQuery])

  const clampedIndex = Math.min(activeIndex, Math.max(filtered.length - 1, 0))

  const runItem = (item: PaletteItem | undefined) => {
    if (!item) return
    setOpen(false)
    item.run()
  }

  const askInAsk = () => {
    setOpen(false)
    navigate(trimmedQuery ? `/ask?q=${encodeURIComponent(trimmedQuery)}` : '/ask')
  }

  const handleKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'ArrowDown') {
      event.preventDefault()
      setActiveIndex((i) => Math.min(i + 1, filtered.length - 1))
    } else if (event.key === 'ArrowUp') {
      event.preventDefault()
      setActiveIndex((i) => Math.max(i - 1, 0))
    } else if (event.key === 'Enter' && (event.metaKey || event.ctrlKey)) {
      event.preventDefault()
      askInAsk()
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
              {filtered.length === 0 && !searchPending && (
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

              {searchPending && (
                <div aria-label="Searching your content">
                  <div className="px-4 pt-2 pb-1 text-[10px] font-mono uppercase tracking-[0.12em] text-text-faint">
                    Content
                  </div>
                  {[0, 1, 2].map((i) => (
                    <div key={i} className="flex items-center gap-3 px-4 py-2">
                      <Skeleton width={14} height={14} rounded />
                      <Skeleton height={13} width={`${70 - i * 12}%`} />
                    </div>
                  ))}
                </div>
              )}

              {searchActive && search.isError && (
                <p className="px-4 py-2 text-[11px] text-text-faint font-mono">
                  search unavailable — navigation still works
                </p>
              )}
            </div>

            <div className="flex items-center gap-4 px-4 py-2.5 border-t border-border text-[11px] text-text-faint font-mono">
              <span className="flex items-center gap-1.5">
                <Kbd>↑↓</Kbd> navigate
              </span>
              <span className="flex items-center gap-1.5">
                <Kbd>↵</Kbd> open
              </span>
              <button
                type="button"
                onClick={askInAsk}
                className="ml-auto flex items-center gap-1.5 hover:text-text-muted cursor-pointer transition-colors"
              >
                ask this in Ask <ArrowRight size={11} aria-hidden /> <Kbd>⌘↵</Kbd>
              </button>
            </div>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>

      {/* Quick capture (E4) */}
      <QuickCaptureModal open={captureOpen} onOpenChange={setCaptureOpen} />
    </>
  )
}
