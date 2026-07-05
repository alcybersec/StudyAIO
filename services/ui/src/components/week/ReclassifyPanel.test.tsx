import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { ReclassifyPanel } from './ReclassifyPanel'
import { artifactsApi, coursesApi } from '../../api/endpoints'
import type { Artifact } from '../../types'

vi.mock('../../api/endpoints', () => ({
  coursesApi: {
    list: vi.fn(),
  },
  artifactsApi: {
    reclassify: vi.fn(),
  },
}))

const artifact: Artifact = {
  id: 'art-1',
  course_id: 'c1',
  week: 9,
  title: null,
  original_filename: 'week9_forensics.pdf',
  file_type: 'pdf',
  sha256: 'abc',
  file_size_bytes: 2048,
  status: 'processed',
  created_at: '2026-01-01T00:00:00Z',
}

const courses = [
  { id: 'c1', code: 'CSIT302', name: 'Cybersecurity', term: null, created_at: '', updated_at: '', weeks_covered: 9, total_artifacts: 4, last_updated: null },
  { id: 'c2', code: 'CSCI368', name: 'Network Security', term: null, created_at: '', updated_at: '', weeks_covered: 7, total_artifacts: 2, last_updated: null },
]

function renderPanel(onClose = vi.fn()) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <ReclassifyPanel artifact={artifact} courseCode="CSIT302" week={9} onClose={onClose} />
      </MemoryRouter>
    </QueryClientProvider>,
  )
  return { onClose }
}

describe('ReclassifyPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(coursesApi.list).mockResolvedValue(courses)
    vi.mocked(artifactsApi.reclassify).mockResolvedValue({
      artifact_id: 'art-1',
      course_code: 'CSCI368',
      week: 7,
      summaries_enqueued: 2,
    })
  })

  it('shows the current placement and target filename', async () => {
    renderPanel()
    expect(screen.getByText('week9_forensics.pdf')).toBeInTheDocument()
    expect(screen.getByText('CSIT302 · Week 9')).toBeInTheDocument()
  })

  it('submits the mutation with the chosen course and week, then closes', async () => {
    const user = userEvent.setup()
    const { onClose } = renderPanel()

    // pick the destination course
    await user.click(await screen.findByLabelText('Move to course'))
    await user.click(await screen.findByText('CSCI368 — Network Security'))

    // change the week
    const weekField = screen.getByLabelText('Week')
    await user.clear(weekField)
    await user.type(weekField, '7')

    await user.click(screen.getByRole('button', { name: 'Move' }))

    await waitFor(() => {
      expect(artifactsApi.reclassify).toHaveBeenCalledWith('art-1', { course_code: 'CSCI368', week: 7 })
    })
    await waitFor(() => expect(onClose).toHaveBeenCalled())
  })

  it('disables Move when nothing changed', async () => {
    renderPanel()
    expect(screen.getByRole('button', { name: 'Move' })).toBeDisabled()
  })

  it('disables Move and shows an error for a non-numeric week', async () => {
    const user = userEvent.setup()
    renderPanel()
    const weekField = screen.getByLabelText('Week')
    await user.clear(weekField)
    await user.type(weekField, 'abc')
    expect(screen.getByRole('button', { name: 'Move' })).toBeDisabled()
    expect(screen.getByRole('alert')).toHaveTextContent('0–52')
  })

  it('keeps the panel open when the mutation fails', async () => {
    vi.mocked(artifactsApi.reclassify).mockRejectedValue(new Error('boom'))
    const user = userEvent.setup()
    const { onClose } = renderPanel()

    await user.click(await screen.findByLabelText('Move to course'))
    await user.click(await screen.findByText('CSCI368 — Network Security'))
    await user.click(screen.getByRole('button', { name: 'Move' }))

    await waitFor(() => expect(artifactsApi.reclassify).toHaveBeenCalled())
    expect(onClose).not.toHaveBeenCalled()
  })

  it('calls onClose from the Cancel button', async () => {
    const user = userEvent.setup()
    const { onClose } = renderPanel()
    await user.click(screen.getByRole('button', { name: 'Cancel' }))
    expect(onClose).toHaveBeenCalled()
  })
})
