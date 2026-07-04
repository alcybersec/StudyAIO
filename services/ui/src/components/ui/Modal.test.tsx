import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Modal } from './Modal'
import { Button } from './Button'

function renderModal(onOpenChange = vi.fn()) {
  render(
    <Modal open onOpenChange={onOpenChange} title="Delete course?" description="This can't be undone.">
      <Button variant="secondary">Cancel</Button>
      <Button variant="danger">Delete</Button>
    </Modal>,
  )
  return { onOpenChange }
}

describe('Modal', () => {
  it('renders a dialog labelled by its title (aria-labelledby)', () => {
    renderModal()
    const dialog = screen.getByRole('dialog')
    const labelledBy = dialog.getAttribute('aria-labelledby')
    expect(labelledBy).toBeTruthy()
    expect(document.getElementById(labelledBy!)).toHaveTextContent('Delete course?')
  })

  it('calls onOpenChange(false) on escape', async () => {
    const user = userEvent.setup()
    const { onOpenChange } = renderModal()
    await user.keyboard('{Escape}')
    expect(onOpenChange).toHaveBeenCalledWith(false)
  })

  it('traps focus inside the dialog while open', async () => {
    const user = userEvent.setup()
    renderModal()
    const dialog = screen.getByRole('dialog')
    for (let i = 0; i < 6; i++) {
      await user.tab()
      expect(dialog.contains(document.activeElement)).toBe(true)
    }
  })

  it('renders nothing when closed', () => {
    render(
      <Modal open={false} onOpenChange={() => {}} title="Hidden">
        <p>Body</p>
      </Modal>,
    )
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })
})
