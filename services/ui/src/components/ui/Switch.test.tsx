import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Switch } from './Switch'

describe('Switch', () => {
  it('renders role=switch associated with its label', () => {
    render(<Switch label="Dark mode" checked={false} onCheckedChange={() => {}} />)
    const el = screen.getByLabelText('Dark mode')
    expect(el).toHaveAttribute('role', 'switch')
  })

  it('reflects checked state via aria-checked', () => {
    const { rerender } = render(<Switch label="Sync" checked={false} onCheckedChange={() => {}} />)
    expect(screen.getByRole('switch')).toHaveAttribute('aria-checked', 'false')
    rerender(<Switch label="Sync" checked onCheckedChange={() => {}} />)
    expect(screen.getByRole('switch')).toHaveAttribute('aria-checked', 'true')
  })

  it('calls onCheckedChange on click', async () => {
    const user = userEvent.setup()
    const onCheckedChange = vi.fn()
    render(<Switch label="Notify" checked={false} onCheckedChange={onCheckedChange} />)
    await user.click(screen.getByRole('switch'))
    expect(onCheckedChange).toHaveBeenCalledWith(true)
  })

  it('toggles with the keyboard (space)', async () => {
    const user = userEvent.setup()
    const onCheckedChange = vi.fn()
    render(<Switch label="Notify" checked={false} onCheckedChange={onCheckedChange} />)
    screen.getByRole('switch').focus()
    await user.keyboard(' ')
    expect(onCheckedChange).toHaveBeenCalledWith(true)
  })

  it('does not fire when disabled', async () => {
    const user = userEvent.setup()
    const onCheckedChange = vi.fn()
    render(<Switch label="Locked" checked={false} onCheckedChange={onCheckedChange} disabled />)
    await user.click(screen.getByRole('switch')).catch(() => {})
    expect(onCheckedChange).not.toHaveBeenCalled()
  })
})
