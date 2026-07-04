import { beforeEach, describe, expect, it, vi } from 'vitest'
import { act, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { CommandPalette } from './CommandPalette'
import { openCommandPalette } from '../lib/commandPalette'

const mockUseCourses = vi.fn()

vi.mock('../hooks/useApi', () => ({
  useCourses: () => mockUseCourses(),
}))

function LocationProbe() {
  const location = useLocation()
  return <span data-testid="path">{location.pathname}</span>
}

function setup() {
  mockUseCourses.mockReturnValue({
    data: [
      { id: 'c1', code: 'CSIT302', name: 'Cybersecurity', weeks_covered: 9 },
      { id: 'c2', code: 'CSCI368', name: 'Networks', weeks_covered: 7 },
    ],
  })
  return render(
    <MemoryRouter>
      <Routes>
        <Route path="*" element={<LocationProbe />} />
      </Routes>
      <CommandPalette />
    </MemoryRouter>,
  )
}

async function openPalette() {
  act(() => openCommandPalette())
  return await screen.findByRole('combobox', { name: /search/i })
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('CommandPalette', () => {
  it('is closed until the open event fires', () => {
    setup()
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('opens on the palette event and shows the Actions section', async () => {
    setup()
    await openPalette()
    expect(screen.getByText(/actions/i)).toBeInTheDocument()
    expect(screen.getByText(/start study session/i)).toBeInTheDocument()
    expect(screen.getByText(/upload files/i)).toBeInTheDocument()
    expect(screen.getByText(/quick capture/i)).toBeInTheDocument()
    expect(screen.getByText(/toggle theme/i)).toBeInTheDocument()
  })

  it('lists courses from the query cache in the Navigate section', async () => {
    setup()
    await openPalette()
    expect(screen.getByText('CSIT302')).toBeInTheDocument()
    expect(screen.getByText('CSCI368')).toBeInTheDocument()
  })

  it('hides the content search section while searchAvailable is false', async () => {
    setup()
    await openPalette()
    expect(screen.queryByText(/content/i)).not.toBeInTheDocument()
  })

  it('filters items as the user types', async () => {
    const u = userEvent.setup()
    setup()
    const input = await openPalette()
    await u.type(input, 'upload')
    expect(screen.getByText(/upload files/i)).toBeInTheDocument()
    expect(screen.queryByText(/start study session/i)).not.toBeInTheDocument()
  })

  it('navigates with arrows and fires the action on Enter', async () => {
    const u = userEvent.setup()
    setup()
    const input = await openPalette()
    // first item is "Start study session"; ArrowDown selects "Upload files"
    await u.type(input, '{ArrowDown}{Enter}')
    expect(screen.getByTestId('path')).toHaveTextContent('/upload')
    // palette closes after firing
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('runs the first action on Enter (start study session)', async () => {
    const u = userEvent.setup()
    setup()
    const input = await openPalette()
    await u.type(input, '{Enter}')
    expect(screen.getByTestId('path')).toHaveTextContent('/study')
  })

  it('navigates to a course on Enter', async () => {
    const u = userEvent.setup()
    setup()
    const input = await openPalette()
    await u.type(input, 'CSIT302')
    await u.type(input, '{Enter}')
    expect(screen.getByTestId('path')).toHaveTextContent('/courses/CSIT302')
  })

  it('shows a coming-soon modal for quick capture', async () => {
    const u = userEvent.setup()
    setup()
    const input = await openPalette()
    await u.type(input, 'capture')
    await u.type(input, '{Enter}')
    expect(await screen.findByText(/coming soon/i)).toBeInTheDocument()
  })

  it('closes on Escape', async () => {
    const u = userEvent.setup()
    setup()
    await openPalette()
    await u.keyboard('{Escape}')
    expect(screen.queryByRole('combobox')).not.toBeInTheDocument()
  })
})
