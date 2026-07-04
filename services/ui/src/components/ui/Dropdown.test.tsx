import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Dropdown, DropdownItem, DropdownSeparator } from './Dropdown'
import { Button } from './Button'

function renderMenu(onRename = vi.fn(), onDelete = vi.fn()) {
  render(
    <Dropdown trigger={<Button variant="secondary">Manage</Button>}>
      <DropdownItem onSelect={onRename}>Rename course</DropdownItem>
      <DropdownItem>Archive course</DropdownItem>
      <DropdownSeparator />
      <DropdownItem danger onSelect={onDelete}>
        Delete course…
      </DropdownItem>
    </Dropdown>,
  )
  return { onRename, onDelete }
}

describe('Dropdown', () => {
  it('opens on click and lists the items', async () => {
    const user = userEvent.setup()
    renderMenu()
    await user.click(screen.getByRole('button', { name: 'Manage' }))
    expect(await screen.findByRole('menu')).toBeInTheDocument()
    expect(screen.getByRole('menuitem', { name: 'Rename course' })).toBeInTheDocument()
    expect(screen.getByRole('menuitem', { name: 'Delete course…' })).toBeInTheDocument()
  })

  it('supports keyboard navigation and selects with enter', async () => {
    const user = userEvent.setup()
    const { onRename } = renderMenu()
    const trigger = screen.getByRole('button', { name: 'Manage' })
    trigger.focus()
    await user.keyboard('{Enter}')
    await screen.findByRole('menu')
    await user.keyboard('{Enter}')
    expect(onRename).toHaveBeenCalledTimes(1)
  })

  it('closes on escape and restores focus to the trigger', async () => {
    const user = userEvent.setup()
    renderMenu()
    const trigger = screen.getByRole('button', { name: 'Manage' })
    await user.click(trigger)
    await screen.findByRole('menu')
    await user.keyboard('{Escape}')
    expect(screen.queryByRole('menu')).not.toBeInTheDocument()
    expect(trigger).toHaveFocus()
  })

  it('marks danger items with the danger tone', async () => {
    const user = userEvent.setup()
    renderMenu()
    await user.click(screen.getByRole('button', { name: 'Manage' }))
    const item = await screen.findByRole('menuitem', { name: 'Delete course…' })
    expect(item.className).toContain('text-red-fg')
  })
})
