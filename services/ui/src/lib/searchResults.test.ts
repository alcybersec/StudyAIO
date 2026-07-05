import { describe, expect, it } from 'vitest'
import { Copy, FileText, Layers, MessageSquare } from 'lucide-react'
import type { GlobalSearchResult } from '../types'
import {
  searchResultHref,
  searchResultIcon,
  searchResultSection,
  searchResultSub,
} from './searchResults'

function result(kind: string, href_meta: Record<string, string | number>): GlobalSearchResult {
  return { kind, title: 't', snippet: 's', href_meta }
}

describe('searchResultHref', () => {
  it('maps a course result to the course page', () => {
    expect(searchResultHref(result('course', { course_code: 'CSIT302' }))).toBe(
      '/courses/CSIT302',
    )
  })

  it('maps a course_week result to the week view', () => {
    expect(
      searchResultHref(result('course_week', { course_code: 'CSIT302', week: 9, summary_id: 'x' })),
    ).toBe('/courses/CSIT302/weeks/9')
  })

  it('maps a flashcard result to a scoped study session', () => {
    expect(
      searchResultHref(result('flashcard', { course_code: 'CSCI368', week: 3, flashcard_id: 'f' })),
    ).toBe('/study?course=CSCI368&week=3')
  })

  it('maps a chat_session result to Ask with the session selected', () => {
    expect(searchResultHref(result('chat_session', { session_id: 'abc' }))).toBe(
      '/ask?session=abc',
    )
  })

  it('returns null for unknown kinds or missing meta', () => {
    expect(searchResultHref(result('mystery', {}))).toBeNull()
    expect(searchResultHref(result('course', {}))).toBeNull()
    expect(searchResultHref(result('course_week', { course_code: 'X' }))).toBeNull()
  })
})

describe('searchResultSection', () => {
  it('groups courses and weeks together, content separately', () => {
    expect(searchResultSection('course')).toBe('Courses & weeks')
    expect(searchResultSection('course_week')).toBe('Courses & weeks')
    expect(searchResultSection('flashcard')).toBe('Content')
    expect(searchResultSection('chat_session')).toBe('Content')
    expect(searchResultSection('mystery')).toBe('Content')
  })
})

describe('searchResultIcon', () => {
  it('maps each kind to its icon', () => {
    expect(searchResultIcon('course')).toBe(Layers)
    expect(searchResultIcon('course_week')).toBe(FileText)
    expect(searchResultIcon('flashcard')).toBe(Copy)
    expect(searchResultIcon('chat_session')).toBe(MessageSquare)
    expect(searchResultIcon('mystery')).toBe(FileText)
  })
})

describe('searchResultSub', () => {
  it('builds a kind-specific sub-label', () => {
    expect(searchResultSub(result('course', { course_code: 'CSIT302' }))).toBe('course')
    expect(searchResultSub(result('course_week', { course_code: 'C', week: 9 }))).toBe('summary · wk 9')
    expect(searchResultSub(result('flashcard', { course_code: 'CSIT302', week: 7 }))).toBe(
      'flashcard · CSIT302 wk 7',
    )
    expect(searchResultSub(result('chat_session', { session_id: 's' }))).toBe('chat session')
  })
})
