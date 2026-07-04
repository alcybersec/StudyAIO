import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ErrorState } from './ErrorState'

describe('ErrorState', () => {
  it('renders as role=alert with the title', () => {
    render(<ErrorState title="Course content couldn't load" onRetry={() => {}} />)
    expect(screen.getByRole('alert')).toHaveTextContent("Course content couldn't load")
  })

  it('fires the retry callback', async () => {
    const user = userEvent.setup()
    const onRetry = vi.fn()
    render(<ErrorState onRetry={onRetry} />)
    await user.click(screen.getByRole('button', { name: /retry/i }))
    expect(onRetry).toHaveBeenCalledTimes(1)
  })

  it('hides the retry button when no callback is given', () => {
    render(<ErrorState detail="boom" />)
    expect(screen.queryByRole('button', { name: /retry/i })).not.toBeInTheDocument()
  })

  it('toggles the collapsible details', async () => {
    const user = userEvent.setup()
    render(<ErrorState onRetry={() => {}} detail="GET /api/x → 500" />)
    const details = screen.getByText('details').closest('details') as HTMLDetailsElement
    expect(details.open).toBe(false)
    await user.click(screen.getByText('details'))
    expect(details.open).toBe(true)
    expect(screen.getByText('GET /api/x → 500')).toBeInTheDocument()
  })
})
