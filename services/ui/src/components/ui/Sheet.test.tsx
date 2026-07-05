import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { Sheet } from './Sheet'

describe('Sheet', () => {
  it('always exposes an accessible name (Radix DialogTitle requirement)', () => {
    render(
      <Sheet open onOpenChange={() => {}} title="Notifications" titleVisible={false}>
        <p>content</p>
      </Sheet>,
    )
    // The dialog is labelled even though the title is visually hidden.
    expect(screen.getByRole('dialog', { name: 'Notifications' })).toBeInTheDocument()
  })

  it('renders a visible heading when titleVisible is true', () => {
    render(
      <Sheet open onOpenChange={() => {}} title="Library">
        <p>content</p>
      </Sheet>,
    )
    const heading = screen.getByText('Library')
    expect(heading).toBeInTheDocument()
    expect(heading).not.toHaveClass('sr-only')
  })
})
