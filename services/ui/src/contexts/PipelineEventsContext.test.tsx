import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { act, render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Link, MemoryRouter, Route, Routes } from 'react-router-dom'
import userEvent from '@testing-library/user-event'
import { PipelineEventsProvider } from './PipelineEventsContext'
import { usePipelineProgress } from './pipelineProgress'
import { PipelineActivityChip } from '../components/ui/PipelineActivityChip'

type Listener = (e: MessageEvent) => void
class FakeEventSource {
  static instances: FakeEventSource[] = []
  closed = false
  onopen: (() => void) | null = null
  onerror: (() => void) | null = null
  listeners: Record<string, Listener> = {}
  url: string
  constructor(url: string) {
    this.url = url
    FakeEventSource.instances.push(this)
  }
  addEventListener(n: string, fn: Listener) {
    this.listeners[n] = fn
  }
  close() {
    this.closed = true
  }
  emit(obj: unknown) {
    this.listeners.pipeline({ data: typeof obj === 'string' ? obj : JSON.stringify(obj) } as MessageEvent)
  }
}
const src = () => FakeEventSource.instances[0]
const ev = (stage: string, status: string, id = 'a1') => ({ artifact_id: id, stage, status, message: null })

function Upload() {
  const { events } = usePipelineProgress()
  return <div data-testid="count">{events.length}</div>
}

function setup() {
  const qc = new QueryClient()
  const invalidate = vi.spyOn(qc, 'invalidateQueries')
  render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={['/upload']}>
        <PipelineEventsProvider>
          <PipelineActivityChip />
          <Link to="/other">go-other</Link>
          <Link to="/upload">go-upload</Link>
          <Routes>
            <Route path="/upload" element={<Upload />} />
            <Route path="/other" element={<p>other page</p>} />
          </Routes>
        </PipelineEventsProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  )
  return { invalidate }
}

describe('PipelineEventsProvider', () => {
  beforeEach(() => {
    FakeEventSource.instances = []
    vi.stubGlobal('EventSource', FakeEventSource)
    vi.spyOn(console, 'error').mockImplementation(() => {})
  })
  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it('keeps one SSE connection across navigation and keeps collecting events', async () => {
    const user = userEvent.setup()
    setup()
    expect(FakeEventSource.instances).toHaveLength(1)
    act(() => src().emit(ev('extract', 'running')))
    await user.click(screen.getByText('go-other'))
    expect(screen.getByText('other page')).toBeInTheDocument()
    act(() => src().emit(ev('summarize', 'running')))
    await user.click(screen.getByText('go-upload'))
    expect(screen.getByTestId('count')).toHaveTextContent('2')
    expect(FakeEventSource.instances).toHaveLength(1)
    expect(src().closed).toBe(false)
  })

  it('shows a global indicator off the Upload page while an artifact is in flight', async () => {
    const user = userEvent.setup()
    setup()
    act(() => src().emit(ev('extract', 'running')))
    expect(screen.queryByRole('status')).not.toBeInTheDocument() // on /upload
    await user.click(screen.getByText('go-other'))
    expect(screen.getByRole('status')).toHaveTextContent('1')
    act(() => src().emit(ev('assets', 'completed')))
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })

  it('invalidates course, week and dashboard queries when an artifact reaches a terminal state', () => {
    const { invalidate } = setup()
    act(() => src().emit(ev('extract', 'running')))
    expect(invalidate).not.toHaveBeenCalled()
    act(() => src().emit(ev('assets', 'completed')))
    const keys = invalidate.mock.calls.map((c) => (c[0] as { queryKey: string[] }).queryKey[0])
    expect(keys).toEqual(expect.arrayContaining(['courses', 'dashboard']))
  })

  it('also invalidates on failure, and ignores malformed frames', () => {
    const { invalidate } = setup()
    act(() => src().emit('{oops'))
    expect(invalidate).not.toHaveBeenCalled()
    act(() => src().emit(ev('extract', 'failed')))
    expect(invalidate).toHaveBeenCalled()
  })
})
