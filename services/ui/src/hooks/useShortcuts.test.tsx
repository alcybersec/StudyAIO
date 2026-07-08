import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { useShortcuts } from './useShortcuts'

const onOpenPalette = vi.fn()
const onOpenOverlay = vi.fn()

function Harness() {
  useShortcuts({ onOpenPalette, onOpenOverlay })
  const location = useLocation()
  return (
    <div>
      <span data-testid="path">{location.pathname}</span>
      <input aria-label="text field" />
      <div role="dialog" data-state="closed" data-testid="dialog" />
    </div>
  )
}

function setup(initialPath = '/') {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <Routes>
        <Route path="*" element={<Harness />} />
      </Routes>
    </MemoryRouter>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('useShortcuts', () => {
  it('opens the palette on ⌘K', async () => {
    const u = userEvent.setup()
    setup()
    await u.keyboard('{Meta>}k{/Meta}')
    expect(onOpenPalette).toHaveBeenCalledTimes(1)
  })

  it('opens the palette on Ctrl+K', async () => {
    const u = userEvent.setup()
    setup()
    await u.keyboard('{Control>}k{/Control}')
    expect(onOpenPalette).toHaveBeenCalledTimes(1)
  })

  it('navigates to /study on S', async () => {
    const u = userEvent.setup()
    setup()
    await u.keyboard('s')
    expect(screen.getByTestId('path')).toHaveTextContent('/study')
  })

  it('navigates to /upload on U', async () => {
    const u = userEvent.setup()
    setup()
    await u.keyboard('u')
    expect(screen.getByTestId('path')).toHaveTextContent('/upload')
  })

  it('opens the shortcut overlay on ?', async () => {
    const u = userEvent.setup()
    setup()
    await u.keyboard('?')
    expect(onOpenOverlay).toHaveBeenCalledTimes(1)
  })

  it('handles the g-h sequence (go home)', async () => {
    const u = userEvent.setup()
    setup('/upload')
    await u.keyboard('gh')
    expect(screen.getByTestId('path')).toHaveTextContent(/^\/$/)
  })

  it('handles the g-s sequence (go study)', async () => {
    const u = userEvent.setup()
    setup()
    await u.keyboard('gs')
    expect(screen.getByTestId('path')).toHaveTextContent('/study')
  })

  it('never fires single-key shortcuts while typing in an input', async () => {
    const u = userEvent.setup()
    setup()
    await u.click(screen.getByRole('textbox', { name: /text field/i }))
    await u.keyboard('sus?')
    expect(screen.getByTestId('path')).toHaveTextContent(/^\/$/)
    expect(onOpenOverlay).not.toHaveBeenCalled()
  })

  it('still opens the palette with ⌘K from inside an input', async () => {
    const u = userEvent.setup()
    setup()
    await u.click(screen.getByRole('textbox', { name: /text field/i }))
    await u.keyboard('{Meta>}k{/Meta}')
    expect(onOpenPalette).toHaveBeenCalledTimes(1)
  })

  it('suppresses single-key shortcuts while a dialog is open, but not ⌘K', async () => {
    const u = userEvent.setup()
    setup()
    screen.getByTestId('dialog').setAttribute('data-state', 'open')
    await u.keyboard('s')
    expect(screen.getByTestId('path')).toHaveTextContent(/^\/$/)
    await u.keyboard('{Meta>}k{/Meta}')
    expect(onOpenPalette).toHaveBeenCalledTimes(1)
  })

  it('does not navigate on modified single keys (e.g. ⌘S)', async () => {
    const u = userEvent.setup()
    setup()
    await u.keyboard('{Meta>}s{/Meta}')
    expect(screen.getByTestId('path')).toHaveTextContent(/^\/$/)
  })
})
