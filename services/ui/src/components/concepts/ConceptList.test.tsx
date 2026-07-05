import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { ConceptList } from './ConceptList'
import type { ConceptNode } from '../../types'

function makeConcept(id: string, name: string): ConceptNode {
  return {
    id,
    name,
    description: `About ${name}`,
    category: 'theory',
    mention_count: 2,
    source_weeks: [1, 3],
    course_id: 'c1',
    created_at: null,
  }
}

const concepts = [
  makeConcept('a', 'ASLR'),
  makeConcept('b', 'ROP chains'),
  makeConcept('c', 'TLS 1.3'),
]

describe('ConceptList keyboard navigation', () => {
  it('uses a roving tabindex — only one row is tabbable', () => {
    render(<ConceptList concepts={concepts} />)
    const rows = screen.getAllByRole('option')
    expect(rows).toHaveLength(3)
    expect(rows.filter((r) => r.tabIndex === 0)).toHaveLength(1)
    expect(rows.filter((r) => r.tabIndex === -1)).toHaveLength(2)
  })

  it('moves focus with arrow keys', async () => {
    const user = userEvent.setup()
    render(<ConceptList concepts={concepts} />)
    const rows = screen.getAllByRole('option')

    rows[0].focus()
    await user.keyboard('{ArrowDown}')
    expect(document.activeElement).toBe(rows[1])

    await user.keyboard('{ArrowDown}')
    expect(document.activeElement).toBe(rows[2])

    // Clamped at the end
    await user.keyboard('{ArrowDown}')
    expect(document.activeElement).toBe(rows[2])

    await user.keyboard('{ArrowUp}')
    expect(document.activeElement).toBe(rows[1])

    await user.keyboard('{Home}')
    expect(document.activeElement).toBe(rows[0])

    await user.keyboard('{End}')
    expect(document.activeElement).toBe(rows[2])
  })

  it('opens the focused concept with Enter', async () => {
    const user = userEvent.setup()
    const onSelect = vi.fn()
    render(<ConceptList concepts={concepts} onSelect={onSelect} />)
    const rows = screen.getAllByRole('option')

    rows[0].focus()
    await user.keyboard('{ArrowDown}')
    await user.keyboard('{Enter}')

    expect(onSelect).toHaveBeenCalledWith('b')
  })

  it('marks the selected concept with aria-selected', () => {
    render(<ConceptList concepts={concepts} selectedId="c" />)
    const rows = screen.getAllByRole('option')
    expect(rows[2]).toHaveAttribute('aria-selected', 'true')
    expect(rows[0]).toHaveAttribute('aria-selected', 'false')
  })

  it('shows a quiet empty message when there are no matches', () => {
    render(<ConceptList concepts={[]} />)
    expect(screen.getByText(/no concepts found/i)).toBeInTheDocument()
  })
})
