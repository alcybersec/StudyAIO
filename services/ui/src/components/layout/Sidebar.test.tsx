import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { Sidebar } from './Sidebar'

const mockUseAuth = vi.fn()
const mockUseDashboard = vi.fn()
const mockUseCourses = vi.fn()

vi.mock('../../hooks/useAuth', () => ({
  useAuth: () => mockUseAuth(),
}))
vi.mock('../../hooks/useApi', () => ({
  useDashboard: () => mockUseDashboard(),
  useCourses: () => mockUseCourses(),
}))

const user = {
  id: 'u1',
  username: 'alex',
  email: 'alex@example.com',
  role: 'user',
  tier: 'free',
  avatar_url: null,
}

function setup({ role = 'user', pending = 3 }: { role?: string; pending?: number } = {}) {
  mockUseAuth.mockReturnValue({
    user: { ...user, role },
    isSelfHosted: true,
    isDemo: false,
    logout: vi.fn(),
  })
  mockUseDashboard.mockReturnValue({ data: { pending_review_count: pending } })
  mockUseCourses.mockReturnValue({
    data: [
      { id: 'c1', code: 'CSIT302', name: 'Cybersecurity', weeks_covered: 9 },
      { id: 'c2', code: 'CSCI368', name: 'Networks', weeks_covered: 7 },
    ],
  })
  return render(
    <MemoryRouter>
      <Sidebar />
    </MemoryRouter>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  window.localStorage.clear()
  window.matchMedia ??= (() => ({
    matches: false,
    addEventListener: () => {},
    removeEventListener: () => {},
  })) as unknown as typeof window.matchMedia
})

describe('Sidebar', () => {
  it('renders the activity groups and their items', () => {
    setup()
    // group labels
    expect(screen.getByText(/learn/i)).toBeInTheDocument()
    expect(screen.getByText(/library/i)).toBeInTheDocument()
    expect(screen.getByText(/insights/i)).toBeInTheDocument()
    // items
    expect(screen.getByRole('link', { name: /^home$/i })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /^study$/i })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /ask/i })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /knowledge/i })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /upload/i })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /review inbox/i })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /analytics/i })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /achievements/i })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /settings/i })).toBeInTheDocument()
  })

  it('links Ask to /ask', () => {
    setup()
    expect(screen.getByRole('link', { name: /ask/i })).toHaveAttribute('href', '/ask')
  })

  it('shows the review inbox badge with the pending count', () => {
    setup({ pending: 5 })
    const review = screen.getByRole('link', { name: /review inbox/i })
    expect(review).toHaveTextContent('5')
  })

  it('hides the review badge when there is nothing pending', () => {
    setup({ pending: 0 })
    const review = screen.getByRole('link', { name: /review inbox/i })
    expect(review).not.toHaveTextContent('0')
  })

  it('lists courses under the Library group', () => {
    setup()
    expect(screen.getByRole('link', { name: /CSIT302/ })).toHaveAttribute('href', '/courses/CSIT302')
    expect(screen.getByRole('link', { name: /CSCI368/ })).toHaveAttribute('href', '/courses/CSCI368')
  })

  it('collapses the course list when the Courses disclosure is toggled', async () => {
    const u = userEvent.setup()
    setup()
    await u.click(screen.getByRole('button', { name: /courses/i }))
    expect(screen.queryByRole('link', { name: /CSIT302/ })).not.toBeInTheDocument()
  })

  it('shows the Admin item only for admins', () => {
    setup({ role: 'user' })
    expect(screen.queryByRole('link', { name: /admin/i })).not.toBeInTheDocument()
  })

  it('shows the Admin item for role=admin', () => {
    setup({ role: 'admin' })
    expect(screen.getByRole('link', { name: /admin/i })).toBeInTheDocument()
  })

  it('has a search affordance with the ⌘K hint', () => {
    setup()
    const search = screen.getByRole('button', { name: /search/i })
    expect(search).toHaveTextContent('⌘K')
  })

  it('opens a placeholder notifications panel from the bell button', async () => {
    const u = userEvent.setup()
    setup()
    await u.click(screen.getByRole('button', { name: /notifications/i }))
    expect(await screen.findByText(/notifications arrive here soon/i)).toBeInTheDocument()
  })

  it('persists collapse state to localStorage', async () => {
    const u = userEvent.setup()
    setup()
    await u.click(screen.getByRole('button', { name: /collapse sidebar/i }))
    expect(window.localStorage.getItem('studyaio-sidebar-collapsed')).toBe('true')
    await u.click(screen.getByRole('button', { name: /expand sidebar/i }))
    expect(window.localStorage.getItem('studyaio-sidebar-collapsed')).toBe('false')
  })

  it('restores collapsed state from localStorage', () => {
    window.localStorage.setItem('studyaio-sidebar-collapsed', 'true')
    setup()
    expect(screen.getByRole('button', { name: /expand sidebar/i })).toBeInTheDocument()
  })
})
