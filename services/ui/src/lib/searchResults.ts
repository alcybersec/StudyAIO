/**
 * Pure mapping from GET /api/search results to palette rows.
 *
 * The backend returns `{ kind, title, snippet, href_meta }` — these helpers
 * turn that into a section, icon, sub-label and navigation href so the
 * command palette stays declarative.
 */
import { Copy, FileText, Layers, MessageSquare, type LucideIcon } from 'lucide-react'
import type { GlobalSearchResult } from '../types'

export type SearchSection = 'Courses & weeks' | 'Content'

/** Route for a search result, or null when it can't be resolved. */
export function searchResultHref(result: GlobalSearchResult): string | null {
  const meta = result.href_meta
  switch (result.kind) {
    case 'course':
      return meta.course_code ? `/courses/${meta.course_code}` : null
    case 'course_week':
      return meta.course_code && meta.week != null
        ? `/courses/${meta.course_code}/weeks/${meta.week}`
        : null
    case 'flashcard':
      return meta.course_code && meta.week != null
        ? `/study?course=${meta.course_code}&week=${meta.week}`
        : null
    case 'chat_session':
      return meta.session_id ? `/ask?session=${meta.session_id}` : null
    default:
      return null
  }
}

/** Palette section a result belongs to. */
export function searchResultSection(kind: string): SearchSection {
  return kind === 'course' || kind === 'course_week' ? 'Courses & weeks' : 'Content'
}

const KIND_ICONS: Record<string, LucideIcon> = {
  course: Layers,
  course_week: FileText,
  flashcard: Copy,
  chat_session: MessageSquare,
}

/** Icon for a result kind (falls back to a document icon). */
export function searchResultIcon(kind: string): LucideIcon {
  return KIND_ICONS[kind] ?? FileText
}

/** Human sub-label, e.g. "flashcard · CSIT302 wk 7". */
export function searchResultSub(result: GlobalSearchResult): string {
  const meta = result.href_meta
  switch (result.kind) {
    case 'course':
      return 'course'
    case 'course_week':
      return `summary · wk ${meta.week}`
    case 'flashcard':
      return `flashcard · ${meta.course_code} wk ${meta.week}`
    case 'chat_session':
      return 'chat session'
    default:
      return result.kind
  }
}
