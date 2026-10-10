import { MemoryRouter } from 'react-router-dom'
import { render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { StudyHubPage } from './StudyHubPage'

vi.mock('../components/ui/SyncChip', () => ({ SyncChip: () => null }))
vi.mock('../components/study/PlanTab', () => ({ PlanTab: () => <div>plan</div> }))
vi.mock('../components/study/FlashcardsStudyTab', () => ({ FlashcardsStudyTab: () => <div>fc</div> }))
vi.mock('../components/study/TimedStudyTab', () => ({ TimedStudyTab: () => <div>timed</div> }))
vi.mock('../components/study/ExamsTab', () => ({ ExamsTab: () => <div>exams</div> }))
vi.mock('../components/study/HistoryTab', () => ({ HistoryTab: () => <div>history</div> }))

const renderAt = (url: string) =>
  render(
    <MemoryRouter initialEntries={[url]}>
      <StudyHubPage />
    </MemoryRouter>,
  )

describe('StudyHubPage tab bar (GL#18)', () => {
  afterEach(() => vi.restoreAllMocks())

  it('scrolls inside its own container and never shrinks or wraps tabs', () => {
    renderAt('/study')
    const list = screen.getByRole('tablist')
    expect(list.className).toContain('overflow-x-auto')
    expect(list.className).toContain('max-w-full')
    for (const tab of screen.getAllByRole('tab')) {
      expect(tab.className).toContain('shrink-0')
      expect(tab.className).toContain('whitespace-nowrap')
      expect(tab.className).toContain('min-h-[44px]')
      expect(tab.className).toContain('focus-visible:outline-2')
    }
  })

  it('scrolls the active tab into view', () => {
    const spy = vi.spyOn(Element.prototype, 'scrollIntoView')
    renderAt('/study?tab=history')
    const active = screen.getAllByRole('tab').find((t) => t.getAttribute('data-state') === 'active')
    expect(active).toBeDefined()
    expect(spy.mock.contexts).toContain(active)
    expect(spy).toHaveBeenCalledWith({ block: 'nearest', inline: 'nearest' })
  })
})
