import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { SettingsPage } from './SettingsPage'

vi.mock('../components/settings/sections/AppearanceSection', () => ({
  AppearanceSection: () => <div data-testid="section-appearance" />,
}))
vi.mock('../components/settings/sections/AiProvidersSection', () => ({
  AiProvidersSection: () => <div data-testid="section-ai" />,
}))
vi.mock('../components/settings/sections/PipelineSection', () => ({
  PipelineSection: () => <div data-testid="section-pipeline" />,
}))
vi.mock('../components/settings/sections/NotificationsSettingsSection', () => ({
  NotificationsSettingsSection: () => <div data-testid="section-notifications" />,
}))
vi.mock('../components/settings/sections/CalendarSection', () => ({
  CalendarSection: () => <div data-testid="section-calendar" />,
}))
vi.mock('../components/settings/sections/BillingSettingsSection', () => ({
  BillingSettingsSection: () => <div data-testid="section-billing" />,
}))
vi.mock('../components/settings/sections/AccountSection', () => ({
  AccountSection: () => <div data-testid="section-account" />,
}))

function setup(initialPath = '/settings') {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <Routes>
        <Route path="/settings/:section?" element={<SettingsPage />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('SettingsPage section rail', () => {
  it('shows the appearance section by default', async () => {
    setup()
    expect(await screen.findByTestId('section-appearance')).toBeInTheDocument()
  })

  it('renders the section matching the route param', async () => {
    setup('/settings/billing')
    expect(await screen.findByTestId('section-billing')).toBeInTheDocument()
    expect(screen.queryByTestId('section-appearance')).not.toBeInTheDocument()
  })

  it('falls back to appearance for unknown sections', async () => {
    setup('/settings/nonsense')
    expect(await screen.findByTestId('section-appearance')).toBeInTheDocument()
  })

  it('navigates between sections via the rail', async () => {
    const user = userEvent.setup()
    setup()
    await screen.findByTestId('section-appearance')

    await user.click(screen.getByRole('link', { name: /pipeline/i }))
    expect(await screen.findByTestId('section-pipeline')).toBeInTheDocument()

    await user.click(screen.getByRole('link', { name: /ai providers/i }))
    expect(await screen.findByTestId('section-ai')).toBeInTheDocument()
  })

  it('marks the active rail item with aria-current', async () => {
    setup('/settings/calendar')
    await screen.findByTestId('section-calendar')
    expect(screen.getByRole('link', { name: /calendar/i })).toHaveAttribute('aria-current', 'true')
    expect(screen.getByRole('link', { name: /appearance/i })).not.toHaveAttribute('aria-current')
  })
})
