import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { AskComposer } from './AskComposer'
import type { AskScope } from './AskComposer'

const mockUseCourses = vi.fn()

vi.mock('../../hooks/useApi', () => ({
  useCourses: () => mockUseCourses(),
}))

const courses = [
  { id: 'c1', code: 'CSIT302', name: 'Cybersecurity', weeks_covered: 3 },
  { id: 'c2', code: 'CSCI368', name: 'Networks', weeks_covered: 2 },
]

function setup({
  scope = { courseCode: null, week: null } as AskScope,
  disabled = false,
} = {}) {
  mockUseCourses.mockReturnValue({ data: courses })
  const onSend = vi.fn()
  const onScopeChange = vi.fn()
  render(
    <AskComposer scope={scope} onScopeChange={onScopeChange} onSend={onSend} disabled={disabled} />,
  )
  return { onSend, onScopeChange }
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('AskComposer', () => {
  it('sends the trimmed message on Enter', async () => {
    const u = userEvent.setup()
    const { onSend } = setup()
    const input = screen.getByRole('textbox', { name: /ask/i })
    await u.type(input, '  What is ASLR? {Enter}')
    expect(onSend).toHaveBeenCalledWith('What is ASLR?')
    expect(input).toHaveValue('')
  })

  it('does not send empty messages', async () => {
    const u = userEvent.setup()
    const { onSend } = setup()
    await u.type(screen.getByRole('textbox', { name: /ask/i }), '{Enter}')
    expect(onSend).not.toHaveBeenCalled()
  })

  it('adds a course scope chip from the + scope menu', async () => {
    const u = userEvent.setup()
    const { onScopeChange } = setup()
    await u.click(screen.getByRole('button', { name: /scope/i }))
    await u.click(await screen.findByText('CSIT302'))
    expect(onScopeChange).toHaveBeenCalledWith({ courseCode: 'CSIT302', week: null })
  })

  it('shows chips for the active scope and removes them', async () => {
    const u = userEvent.setup()
    const { onScopeChange } = setup({ scope: { courseCode: 'CSIT302', week: 7 } })
    expect(screen.getByText('CSIT302')).toBeInTheDocument()
    expect(screen.getByText(/week 7/i)).toBeInTheDocument()

    await u.click(screen.getByRole('button', { name: /remove week scope/i }))
    expect(onScopeChange).toHaveBeenCalledWith({ courseCode: 'CSIT302', week: null })

    await u.click(screen.getByRole('button', { name: /remove course scope/i }))
    expect(onScopeChange).toHaveBeenCalledWith({ courseCode: null, week: null })
  })

  it('offers week scoping once a course is chosen', async () => {
    const u = userEvent.setup()
    const { onScopeChange } = setup({ scope: { courseCode: 'CSIT302', week: null } })
    await u.click(screen.getByRole('button', { name: /week/i }))
    await u.click(await screen.findByText('Week 2'))
    expect(onScopeChange).toHaveBeenCalledWith({ courseCode: 'CSIT302', week: 2 })
  })

  it('disables the input while streaming', () => {
    setup({ disabled: true })
    expect(screen.getByRole('textbox', { name: /ask/i })).toBeDisabled()
  })
})
