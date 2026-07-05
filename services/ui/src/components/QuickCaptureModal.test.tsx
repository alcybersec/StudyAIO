import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { toast } from 'sonner'
import { uploadApi } from '../api/endpoints'
import { AppApiError } from '../api/errors'
import { captureSchema } from '../lib/schemas'
import { QuickCaptureModal } from './QuickCaptureModal'

vi.mock('../api/endpoints', () => ({
  uploadApi: {
    capture: vi.fn(),
  },
}))

vi.mock('sonner', () => ({
  toast: Object.assign(vi.fn(), {
    success: vi.fn(),
    error: vi.fn(),
  }),
}))

const mockedCapture = vi.mocked(uploadApi.capture)

function renderModal() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  const onOpenChange = vi.fn()
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <QuickCaptureModal open onOpenChange={onOpenChange} />
      </MemoryRouter>
    </QueryClientProvider>,
  )
  return { onOpenChange }
}

describe('captureSchema', () => {
  it('rejects when both text and url are provided', () => {
    const result = captureSchema.safeParse({ text: 'notes', url: 'https://x.dev' })
    expect(result.success).toBe(false)
    expect(result.error?.issues.some((i) => /not both/i.test(i.message))).toBe(true)
  })

  it('rejects when neither text nor url is provided', () => {
    const result = captureSchema.safeParse({ title: 'only a title' })
    expect(result.success).toBe(false)
    expect(result.error?.issues.some((i) => /paste some text or enter a url/i.test(i.message))).toBe(true)
  })

  it('rejects non-http(s) URLs', () => {
    expect(captureSchema.safeParse({ url: 'ftp://files' }).success).toBe(false)
    expect(captureSchema.safeParse({ url: 'not a url' }).success).toBe(false)
  })

  it('accepts text-only and url-only payloads', () => {
    expect(captureSchema.safeParse({ text: 'some notes' }).success).toBe(true)
    expect(captureSchema.safeParse({ url: 'https://example.com/a' }).success).toBe(true)
  })
})

describe('QuickCaptureModal', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('submits a text-only payload (no url key)', async () => {
    const user = userEvent.setup()
    mockedCapture.mockResolvedValue({
      artifact_id: 'a1',
      filename: 'capture.txt',
      status: 'processing',
      pipeline_task_id: null,
    })
    renderModal()

    await user.type(screen.getByLabelText('Text'), 'ASLR notes')
    await user.click(screen.getByRole('button', { name: 'Capture' }))

    await waitFor(() => expect(mockedCapture).toHaveBeenCalledWith({ text: 'ASLR notes' }))
    expect(toast.success).toHaveBeenCalledWith(
      'Capturing — processing started',
      expect.objectContaining({ action: expect.anything() }),
    )
  })

  it('submits a url payload with optional title', async () => {
    const user = userEvent.setup()
    mockedCapture.mockResolvedValue({
      artifact_id: 'a1',
      filename: 'capture.txt',
      status: 'processing',
      pipeline_task_id: null,
    })
    renderModal()

    await user.click(screen.getByRole('tab', { name: 'From URL' }))
    await user.type(screen.getByLabelText('URL'), 'https://example.com/aslr')
    await user.type(screen.getByLabelText('Title (optional)'), 'ASLR article')
    await user.click(screen.getByRole('button', { name: 'Capture' }))

    await waitFor(() =>
      expect(mockedCapture).toHaveBeenCalledWith({
        url: 'https://example.com/aslr',
        title: 'ASLR article',
      }),
    )
  })

  it('shows a field error instead of submitting when the active field is empty', async () => {
    const user = userEvent.setup()
    renderModal()

    await user.click(screen.getByRole('button', { name: 'Capture' }))
    expect(await screen.findByText(/paste some text or enter a url/i)).toBeInTheDocument()
    expect(mockedCapture).not.toHaveBeenCalled()
  })

  it('shows a clear too-large message on 413', async () => {
    const user = userEvent.setup()
    mockedCapture.mockRejectedValue(new AppApiError('Captured text exceeds 1 MB limit', 413))
    renderModal()

    await user.type(screen.getByLabelText('Text'), 'big')
    await user.click(screen.getByRole('button', { name: 'Capture' }))

    await waitFor(() =>
      expect(toast.error).toHaveBeenCalledWith(
        'That capture is too large',
        expect.objectContaining({ description: expect.stringMatching(/under 1 MB/) }),
      ),
    )
  })
})
