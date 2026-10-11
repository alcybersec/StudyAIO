import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { OnboardingTour } from './OnboardingTour'

const { skip, tour } = vi.hoisted(() => {
  const skip = vi.fn()
  // Stable identity: the component re-measures whenever currentStep changes.
  const tour = {
    active: true,
    step: 0,
    currentStep: { target: 'anchor', title: 'Title', description: 'Desc' },
    totalSteps: 3,
    completed: false,
    start: () => {},
    next: () => {},
    prev: () => {},
    skip,
  }
  return { skip, tour }
})

vi.mock('../../hooks/useAuth', () => ({ useAuth: () => ({ isDemo: false }) }))
vi.mock('../../hooks/useTour', () => ({ useTour: () => tour }))

describe('OnboardingTour backdrop', () => {
  it('is a real button that activates from the keyboard', async () => {
    Element.prototype.scrollIntoView = vi.fn()
    render(
      <>
        <div data-tour="anchor" />
        <OnboardingTour />
      </>,
    )
    const backdrop = await screen.findByRole('button', { name: 'Skip tour' })
    expect(backdrop.tagName).toBe('BUTTON')
    backdrop.focus()
    await userEvent.keyboard('{Enter}')
    expect(skip).toHaveBeenCalled()
  })
})
