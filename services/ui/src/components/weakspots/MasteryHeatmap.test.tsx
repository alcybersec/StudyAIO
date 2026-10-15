import { useState } from 'react'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { MasteryHeatmap, MasteryLegend, type HeatmapSelection } from './MasteryHeatmap'
import type { WeakSpotCourse, WeakSpotWeek } from '../../types'

const week = (n: number, status: WeakSpotWeek['status'], weakness: number | null): WeakSpotWeek => ({
  week: n,
  status,
  weakness,
  confidence: 0.5,
  urgency: 0,
  priority: weakness ?? 0,
  evidence: { quiz_attempts: 0, quiz_accuracy: null, cards_reviewed: 0, avg_ease: null, lapsed_cards: 0, overdue_cards: 0 },
  next_exam: null,
})

const COURSES: WeakSpotCourse[] = [
  { course_id: 'c1', course_code: 'CSIT302', weeks: [week(1, 'unknown', null), week(2, 'weak', 0.8), week(3, 'shaky', 0.375), week(4, 'solid', 0.2)] },
  { course_id: 'c2', course_code: 'CSIT314', weeks: [week(1, 'solid', 0.1), week(2, 'unknown', null)] },
]

function Harness() {
  const [sel, setSel] = useState<HeatmapSelection | null>(null)
  return <MasteryHeatmap courses={COURSES} selected={sel} onSelect={setSel} />
}

describe('MasteryHeatmap', () => {
  it('draws the four states and never paints unknown red', () => {
    render(<Harness />)
    const cells = screen.getAllByRole('button')
    const byState = (s: string) => cells.filter((c) => c.getAttribute('data-state') === s)
    expect(byState('unknown')).toHaveLength(2)
    expect(byState('weak')).toHaveLength(1)
    expect(byState('ok')).toHaveLength(1)
    expect(byState('solid')).toHaveLength(2)
    for (const c of byState('unknown')) expect(c.className).not.toMatch(/red/)
    expect(byState('weak')[0].className).toMatch(/red/)
  })

  it('labels each cell in words, not only colour', () => {
    render(<Harness />)
    expect(screen.getByRole('button', { name: /CSIT302 week 1: Not enough data/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /CSIT302 week 2: Weak, weakness 80%/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /CSIT302 week 3: OK/ })).toBeInTheDocument()
  })

  it('has a single tab stop and moves with the arrow keys', async () => {
    const user = userEvent.setup()
    render(<Harness />)
    const cells = screen.getAllByRole('button')
    expect(cells.filter((c) => c.tabIndex === 0)).toHaveLength(1)

    await user.tab()
    expect(cells[0]).toHaveFocus()
    await user.keyboard('{ArrowRight}')
    expect(cells[1]).toHaveFocus()
    await user.keyboard('{ArrowDown}')
    expect(screen.getByRole('button', { name: /CSIT314 week 2/ })).toHaveFocus()
    await user.keyboard('{ArrowUp}{Home}')
    expect(cells[0]).toHaveFocus()
    await user.keyboard('{End}')
    expect(cells[3]).toHaveFocus()
  })

  it('selects a week with Enter', async () => {
    const user = userEvent.setup()
    render(<Harness />)
    const cell = screen.getByRole('button', { name: /CSIT302 week 2/ })
    cell.focus()
    await user.keyboard('{Enter}')
    expect(cell).toHaveAttribute('aria-pressed', 'true')
  })
})

describe('MasteryLegend', () => {
  it('lists all four states by name', () => {
    render(<MasteryLegend />)
    for (const label of ['Not enough data', 'Weak', 'OK', 'Solid']) {
      expect(screen.getByText(label)).toBeInTheDocument()
    }
  })
})
