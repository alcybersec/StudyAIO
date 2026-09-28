import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { FeedbackModal } from './FeedbackModal'
import { useSubmitFeedback } from '../hooks/useApi'

vi.mock('../hooks/useApi', () => ({ useSubmitFeedback: vi.fn() }))
const toastSuccess = vi.fn()
vi.mock('sonner', () => ({ toast: { success: (...a: unknown[]) => toastSuccess(...a) } }))

const asResult = (q: object) => q as never
const mutate = vi.fn()

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(useSubmitFeedback).mockReturnValue(asResult({ mutate, isPending: false }))
})

function open(route = '/courses/CSIT302/weeks/3') {
  render(
    <MemoryRouter initialEntries={[route]}>
      <FeedbackModal open onOpenChange={() => {}} />
    </MemoryRouter>,
  )
  return userEvent.setup()
}

describe('FeedbackModal', () => {
  it('will not send an empty report', () => {
    open()
    expect(screen.getByRole('button', { name: /^send$/i })).toBeDisabled()
  })

  it('will not send whitespace either', async () => {
    const user = open()
    await user.type(screen.getByLabelText(/your feedback/i), '   ')

    expect(screen.getByRole('button', { name: /^send$/i })).toBeDisabled()
  })

  it('attaches the route so the report can be reproduced', async () => {
    // Without this, "the summary looked empty" is unactionable.
    const user = open('/courses/CSIT302/weeks/3')
    await user.type(screen.getByLabelText(/your feedback/i), 'summary is blank')
    await user.click(screen.getByRole('button', { name: /^send$/i }))

    expect(mutate).toHaveBeenCalledWith(
      expect.objectContaining({ route: '/courses/CSIT302/weeks/3', message: 'summary is blank' }),
      expect.anything(),
    )
  })

  it('trims the message before sending', async () => {
    const user = open()
    await user.type(screen.getByLabelText(/your feedback/i), '  spaced out  ')
    await user.click(screen.getByRole('button', { name: /^send$/i }))

    expect(mutate.mock.calls[0][0].message).toBe('spaced out')
  })

  it('sends the kind the reporter picked', async () => {
    const user = open()
    await user.click(screen.getByRole('button', { name: /something confused me/i }))
    await user.type(screen.getByLabelText(/your feedback/i), 'what is a week?')
    await user.click(screen.getByRole('button', { name: /^send$/i }))

    expect(mutate.mock.calls[0][0].kind).toBe('confusing')
  })

  it('keeps the text on the screen when sending fails', async () => {
    // Closing over a failed send would lose what they wrote, which is the one
    // thing guaranteed to stop somebody reporting a second time.
    mutate.mockImplementation((_vars, opts) => opts.onError(new Error('network down')))
    const user = open()
    await user.type(screen.getByLabelText(/your feedback/i), 'important report')
    await user.click(screen.getByRole('button', { name: /^send$/i }))

    expect(await screen.findByRole('alert')).toHaveTextContent(/network down/i)
    expect(screen.getByLabelText(/your feedback/i)).toHaveValue('important report')
  })

  it('thanks the reporter on success', async () => {
    mutate.mockImplementation((_vars, opts) => opts.onSuccess())
    const user = open()
    await user.type(screen.getByLabelText(/your feedback/i), 'nice app')
    await user.click(screen.getByRole('button', { name: /^send$/i }))

    expect(toastSuccess).toHaveBeenCalled()
  })

  it('says what is collected', async () => {
    open()
    expect(screen.getByText(/nothing else is collected/i)).toBeInTheDocument()
  })
})
