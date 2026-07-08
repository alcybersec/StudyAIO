import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { CommandPalette } from './CommandPalette'
import { searchApi } from '../api/search'
import { isSearchAvailable, openCommandPalette } from '../lib/commandPalette'
import type { GlobalSearchResult } from '../types'

const mockUseCourses = vi.fn()

vi.mock('../hooks/useApi', () => ({
  useCourses: () => mockUseCourses(),
}))

vi.mock('../api/search', () => ({
  searchApi: { search: vi.fn() },
}))

vi.mock('../lib/commandPalette', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../lib/commandPalette')>()
  return { ...actual, isSearchAvailable: vi.fn(() => true) }
})

const mockedSearch = vi.mocked(searchApi.search)
const mockedFlag = vi.mocked(isSearchAvailable)

const RESULTS: GlobalSearchResult[] = [
  {
    kind: 'course_week',
    title: 'CSIT302 — Week 9',
    snippet: '…memory forensics…',
    href_meta: { course_code: 'CSIT302', week: 9, summary_id: 's1' },
  },
  {
    kind: 'flashcard',
    title: 'ASLR randomizes stack, heap and library bases',
    snippet: 'ASLR…',
    href_meta: { course_code: 'CSIT302', week: 7, flashcard_id: 'f1' },
  },
  {
    kind: 'chat_session',
    title: 'explain ASLR bypasses',
    snippet: 'explain ASLR bypasses',
    href_meta: { session_id: 'sess1' },
  },
]

function LocationProbe() {
  const location = useLocation()
  return <span data-testid="path">{location.pathname + location.search}</span>
}

function setup() {
  mockUseCourses.mockReturnValue({
    data: [
      { id: 'c1', code: 'CSIT302', name: 'Cybersecurity', weeks_covered: 9 },
      { id: 'c2', code: 'CSCI368', name: 'Networks', weeks_covered: 7 },
    ],
  })
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <Routes>
          <Route path="*" element={<LocationProbe />} />
        </Routes>
        <CommandPalette />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

async function openPalette() {
  act(() => openCommandPalette())
  return await screen.findByRole('combobox', { name: /search/i })
}

beforeEach(() => {
  vi.clearAllMocks()
  mockedFlag.mockReturnValue(true)
  mockedSearch.mockResolvedValue({ query: '', results: [] })
})

afterEach(() => {
  vi.useRealTimers()
})

describe('CommandPalette', () => {
  it('is closed until the open event fires', () => {
    setup()
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('opens on the palette event and shows the Actions section', async () => {
    setup()
    await openPalette()
    expect(screen.getByText(/actions/i)).toBeInTheDocument()
    expect(screen.getByText(/start study session/i)).toBeInTheDocument()
    expect(screen.getByText(/upload files/i)).toBeInTheDocument()
    expect(screen.getByText(/quick capture/i)).toBeInTheDocument()
    expect(screen.getByText(/toggle theme/i)).toBeInTheDocument()
  })

  it('lists courses from the query cache in the Navigate section', async () => {
    setup()
    await openPalette()
    expect(screen.getByText('CSIT302')).toBeInTheDocument()
    expect(screen.getByText('CSCI368')).toBeInTheDocument()
  })

  it('filters items as the user types', async () => {
    const u = userEvent.setup()
    setup()
    const input = await openPalette()
    await u.type(input, 'upload')
    expect(screen.getByText(/upload files/i)).toBeInTheDocument()
    expect(screen.queryByText(/start study session/i)).not.toBeInTheDocument()
  })

  it('navigates with arrows and fires the action on Enter', async () => {
    const u = userEvent.setup()
    setup()
    const input = await openPalette()
    // first item is "Start study session"; ArrowDown selects "Upload files"
    await u.type(input, '{ArrowDown}{Enter}')
    expect(screen.getByTestId('path')).toHaveTextContent('/upload')
    // palette closes after firing
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('runs the first action on Enter (start study session)', async () => {
    const u = userEvent.setup()
    setup()
    const input = await openPalette()
    await u.type(input, '{Enter}')
    expect(screen.getByTestId('path')).toHaveTextContent('/study')
  })

  it('navigates to a course on Enter', async () => {
    const u = userEvent.setup()
    setup()
    const input = await openPalette()
    await u.type(input, 'CSIT302')
    await u.type(input, '{Enter}')
    expect(screen.getByTestId('path')).toHaveTextContent('/courses/CSIT302')
  })

  it('opens the quick capture modal from the capture action', async () => {
    const u = userEvent.setup()
    setup()
    const input = await openPalette()
    await u.type(input, 'capture')
    await u.type(input, '{Enter}')
    expect(await screen.findByText(/paste text or a url straight into the pipeline/i)).toBeInTheDocument()
    expect(screen.getByLabelText('Text')).toBeInTheDocument()
  })

  it('closes on Escape', async () => {
    const u = userEvent.setup()
    setup()
    await openPalette()
    await u.keyboard('{Escape}')
    expect(screen.queryByRole('combobox')).not.toBeInTheDocument()
  })
})

describe('CommandPalette global search', () => {
  it('debounces input and only searches at 2+ characters', async () => {
    setup()
    act(() => openCommandPalette())
    const input = screen.getByRole('combobox', { name: /search/i })
    vi.useFakeTimers()

    // A single character never queries, even after the debounce window.
    fireEvent.change(input, { target: { value: 'a' } })
    await act(async () => {
      await vi.advanceTimersByTimeAsync(300)
    })
    expect(mockedSearch).not.toHaveBeenCalled()

    // 2+ characters query only once the 200ms debounce has elapsed.
    fireEvent.change(input, { target: { value: 'as' } })
    fireEvent.change(input, { target: { value: 'asl' } })
    await act(async () => {
      await vi.advanceTimersByTimeAsync(199)
    })
    expect(mockedSearch).not.toHaveBeenCalled()
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1)
    })
    expect(mockedSearch).toHaveBeenCalledWith('asl')
    expect(mockedSearch).toHaveBeenCalledTimes(1)
  })

  it('renders results grouped by kind with icons and sub-labels', async () => {
    mockedSearch.mockResolvedValue({ query: 'asl', results: RESULTS })
    const u = userEvent.setup()
    setup()
    const input = await openPalette()
    await u.type(input, 'asl')

    expect(await screen.findByText('CSIT302 — Week 9')).toBeInTheDocument()
    expect(screen.getByText('Courses & weeks')).toBeInTheDocument()
    expect(screen.getByText('Content')).toBeInTheDocument()
    expect(screen.getByText('summary · wk 9')).toBeInTheDocument()
    expect(screen.getByText('flashcard · CSIT302 wk 7')).toBeInTheDocument()
    expect(screen.getByText('chat session')).toBeInTheDocument()
  })

  it('navigates to the result href on Enter', async () => {
    mockedSearch.mockResolvedValue({ query: 'asl', results: RESULTS })
    const u = userEvent.setup()
    setup()
    const input = await openPalette()
    await u.type(input, 'asl')
    await screen.findByText('CSIT302 — Week 9')

    // 'asl' filters out every static item, so the first option is the week result.
    await u.keyboard('{Enter}')
    expect(screen.getByTestId('path')).toHaveTextContent('/courses/CSIT302/weeks/9')
  })

  it('escalates the query to Ask on ctrl/cmd+Enter', async () => {
    const u = userEvent.setup()
    setup()
    const input = await openPalette()
    await u.type(input, 'what is aslr')
    await u.keyboard('{Control>}{Enter}{/Control}')
    expect(screen.getByTestId('path')).toHaveTextContent('/ask?q=what%20is%20aslr')
  })

  it('hides the content section and never queries when the flag is off', async () => {
    mockedFlag.mockReturnValue(false)
    const u = userEvent.setup()
    setup()
    const input = await openPalette()
    await u.type(input, 'asl')

    await waitFor(() => expect(screen.getByText('No matches.')).toBeInTheDocument())
    expect(mockedSearch).not.toHaveBeenCalled()
    expect(screen.queryByText('Content')).not.toBeInTheDocument()
  })

  it('shows a compact inline notice when search fails but navigation still works', async () => {
    mockedSearch.mockRejectedValue(new Error('boom'))
    const u = userEvent.setup()
    setup()
    const input = await openPalette()
    await u.type(input, 'csit')

    expect(await screen.findByText(/search unavailable/i)).toBeInTheDocument()
    // The static navigation item still matches and still navigates.
    expect(screen.getByText('CSIT302')).toBeInTheDocument()
    await u.keyboard('{Enter}')
    expect(screen.getByTestId('path')).toHaveTextContent('/courses/CSIT302')
  })
})
