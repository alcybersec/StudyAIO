import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { ChatMessage } from './ChatMessage'
import type { ChatAction, ChatMessage as ChatMessageType } from '../../types'

function Where() {
  const loc = useLocation()
  return <div data-testid="where">{`${loc.pathname}${loc.search}`}</div>
}

function msg(over: Partial<ChatMessageType> = {}): ChatMessageType {
  return {
    id: 'm1',
    session_id: 's1',
    role: 'assistant',
    content: 'Here you go',
    citations_json: null,
    action: null,
    created_at: '2026-10-09T10:00:00Z',
    ...over,
  }
}

function renderMsg(message: ChatMessageType) {
  return render(
    <MemoryRouter initialEntries={['/ask']}>
      <Routes>
        <Route
          path="*"
          element={
            <>
              <ChatMessage message={message} />
              <Where />
            </>
          }
        />
      </Routes>
    </MemoryRouter>,
  )
}

const action: ChatAction = {
  type: 'open_quiz_builder',
  course_code: 'CSCI369',
  course_id: 'c1',
  week: 2,
}

describe('ChatMessage action', () => {
  it('renders an accessible quiz-builder link and navigates with course and week', async () => {
    renderMsg(msg({ action }))
    const link = screen.getByRole('link', { name: 'Open quiz builder for CSCI369 Week 2' })
    await userEvent.click(link)
    const url = new URL(screen.getByTestId('where').textContent ?? '', 'http://x')
    expect(url.pathname).toBe('/study')
    expect(url.searchParams.get('tab')).toBe('exams')
    expect(url.searchParams.get('create')).toBe('1')
    expect(url.searchParams.get('course')).toBe('CSCI369')
    expect(url.searchParams.get('week')).toBe('2')
  })

  it('omits week and course params when the action has none', async () => {
    renderMsg(msg({ action: { ...action, course_code: null, course_id: null, week: null } }))
    await userEvent.click(screen.getByRole('link', { name: 'Open quiz builder' }))
    const url = new URL(screen.getByTestId('where').textContent ?? '', 'http://x')
    expect(url.searchParams.has('course')).toBe(false)
    expect(url.searchParams.has('week')).toBe(false)
  })

  it('renders no action when action is null', () => {
    renderMsg(msg({ action: null }))
    expect(screen.queryByRole('link', { name: /quiz builder/i })).toBeNull()
  })

  it('renders no action when the field is absent', () => {
    const m = msg()
    delete m.action
    renderMsg(m)
    expect(screen.queryByRole('link', { name: /quiz builder/i })).toBeNull()
  })
})

describe('ChatMessage citations with nullable fields', () => {
  it('renders a citation with null week and page_ref', () => {
    renderMsg(
      msg({
        citations_json: [
          { ref: 1, course_code: 'CSCI369', week: null, page_ref: null, artifact_id: 'a1', text_snippet: 's' },
        ],
      }),
    )
    const link = screen.getByRole('link', { name: /\[1\]/ })
    expect(link.textContent).toBe('[1]CSCI369')
    expect(link.getAttribute('href')).toBe('/courses/CSCI369?artifact=a1')
  })

  it('renders a citation with week and page', () => {
    renderMsg(
      msg({
        citations_json: [
          { ref: 2, course_code: 'CSCI369', week: 2, page_ref: 4, artifact_id: 'a1', text_snippet: 's' },
        ],
      }),
    )
    const link = screen.getByRole('link', { name: /\[2\]/ })
    expect(link.getAttribute('href')).toBe('/courses/CSCI369/weeks/2?artifact=a1&page=4')
    expect(link.textContent).toContain('CSCI369 W2')
  })

  it('renders a citation with no course or artifact', () => {
    renderMsg(
      msg({ citations_json: [{ ref: 3, course_code: null, week: null, page_ref: null, artifact_id: null }] }),
    )
    expect(screen.getByRole('link', { name: /\[3\]/ }).getAttribute('href')).toBe('/courses')
  })
})
