import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { UploadPage } from './UploadPage'
import { uploadApi } from '../api/endpoints'
import type { PipelineEvent } from '../types'

vi.mock('../api/endpoints', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../api/endpoints')>()
  return {
    ...actual,
    uploadApi: { ...actual.uploadApi, upload: vi.fn(), batchUpload: vi.fn() },
    coursesApi: {
      ...actual.coursesApi,
      list: vi.fn().mockResolvedValue([
        { id: 'c1', code: 'CSIT302', name: 'Cybersecurity', term: null, created_at: '', updated_at: '', weeks_covered: 1, total_artifacts: 1, last_updated: null },
      ]),
    },
  }
})

vi.mock('../hooks/useAuth', () => ({ useAuth: () => ({ isDemo: false }) }))

let events: PipelineEvent[] = []
vi.mock('../contexts/pipelineProgress', () => ({
  usePipelineProgress: () => ({
    events,
    connectionState: 'open',
    uploads: [],
    activeCount: 0,
    track: vi.fn(),
  }),
}))

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <UploadPage />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

const pdf = (name = 'week3.pdf') => new File(['x'], name, { type: 'application/pdf' })

function fileInput(): HTMLInputElement {
  return document.querySelector('input[type="file"]:not([webkitdirectory])') as HTMLInputElement
}

describe('UploadPage placement', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    events = []
    vi.mocked(uploadApi.upload).mockResolvedValue({ artifact_id: 'art-1', status: 'processing' } as never)
  })

  it('defaults to "Let StudyAIO decide" and sends no placement', async () => {
    const user = userEvent.setup()
    renderPage()
    expect(screen.getByRole('radio', { name: 'Let StudyAIO decide' })).toBeChecked()
    await user.upload(fileInput(), pdf())
    await waitFor(() => expect(uploadApi.upload).toHaveBeenCalled())
    expect(vi.mocked(uploadApi.upload).mock.calls[0][1]).toBeUndefined()
  })

  it('manual placement with a course but no week is blocked: error shown, nothing uploaded', async () => {
    const user = userEvent.setup()
    renderPage()
    await user.click(screen.getByRole('radio', { name: 'Choose course & week' }))
    await user.click(await screen.findByRole('button', { name: 'Course' }))
    await user.click(await screen.findByRole('menuitemradio', { name: 'New course…' }))
    await user.type(screen.getByLabelText('New course code'), 'NEW101')
    expect(await screen.findByText('Enter a week from 1 to 52')).toBeInTheDocument()
    await user.upload(fileInput(), pdf())
    expect(uploadApi.upload).not.toHaveBeenCalled()
  })

  it('manual placement with a week but no course is blocked too', async () => {
    const user = userEvent.setup()
    renderPage()
    await user.click(screen.getByRole('radio', { name: 'Choose course & week' }))
    await screen.findByRole('button', { name: 'Course' })
    await user.type(screen.getByLabelText('Week'), '4')
    expect(await screen.findByText('Choose a course, or let StudyAIO decide')).toBeInTheDocument()
    await user.upload(fileInput(), pdf())
    expect(uploadApi.upload).not.toHaveBeenCalled()
  })

  it('a typed new course and week are sent together with the upload', async () => {
    const user = userEvent.setup()
    renderPage()
    await user.click(screen.getByRole('radio', { name: 'Choose course & week' }))
    // The user has one course, so the code box appears after choosing "New course…".
    await user.click(await screen.findByRole('button', { name: 'Course' }))
    await user.click(await screen.findByRole('menuitemradio', { name: 'New course…' }))
    await user.type(screen.getByLabelText('New course code'), 'NEW101')
    await user.type(screen.getByLabelText('Week'), '7')
    await user.upload(fileInput(), pdf())
    await waitFor(() => expect(uploadApi.upload).toHaveBeenCalled())
    expect(vi.mocked(uploadApi.upload).mock.calls[0][1]).toEqual({ course_code: 'NEW101', week: 7 })
  })

  it('an existing course picked from the list is sent as-is', async () => {
    const user = userEvent.setup()
    renderPage()
    await user.click(screen.getByRole('radio', { name: 'Choose course & week' }))
    await user.click(await screen.findByRole('button', { name: 'Course' }))
    await user.click(await screen.findByRole('menuitemradio', { name: /CSIT302/ }))
    await user.type(screen.getByLabelText('Week'), '2')
    await user.upload(fileInput(), pdf())
    await waitFor(() => expect(uploadApi.upload).toHaveBeenCalled())
    expect(vi.mocked(uploadApi.upload).mock.calls[0][1]).toEqual({ course_code: 'CSIT302', week: 2 })
  })

  it('batch uploads carry the same placement', async () => {
    const user = userEvent.setup()
    vi.mocked(uploadApi.batchUpload).mockResolvedValue({
      total: 3, succeeded: 3, duplicates: 0, failed: 0,
      results: [1, 2, 3].map((n) => ({ artifact_id: `a${n}`, status: 'processing' })),
    } as never)
    renderPage()
    await user.click(screen.getByRole('radio', { name: 'Choose course & week' }))
    await user.click(await screen.findByRole('button', { name: 'Course' }))
    await user.click(await screen.findByRole('menuitemradio', { name: /CSIT302/ }))
    await user.type(screen.getByLabelText('Week'), '9')
    await user.upload(fileInput(), [pdf('a.pdf'), pdf('b.pdf'), pdf('c.pdf')])
    await waitFor(() => expect(uploadApi.batchUpload).toHaveBeenCalled())
    expect(vi.mocked(uploadApi.batchUpload).mock.calls[0][1]).toEqual({ course_code: 'CSIT302', week: 9 })
  })

  it('a placed upload shows ingest and classify as done while extract is the first event', async () => {
    const user = userEvent.setup()
    events = [{ artifact_id: 'art-1', stage: 'extract', status: 'started', message: null }]
    renderPage()
    await user.click(screen.getByRole('radio', { name: 'Choose course & week' }))
    await user.click(await screen.findByRole('button', { name: 'Course' }))
    await user.click(await screen.findByRole('menuitemradio', { name: /CSIT302/ }))
    await user.type(screen.getByLabelText('Week'), '1')
    await user.upload(fileInput(), pdf())
    await screen.findByText('week3.pdf')
    expect(await screen.findByRole('listitem', { name: 'ingest: done' })).toBeInTheDocument()
    expect(screen.getByRole('listitem', { name: 'classify: done' })).toBeInTheDocument()
    expect(screen.getByRole('listitem', { name: 'extract: running' })).toBeInTheDocument()
  })
})
