import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { TimeZoneField } from './TimeZoneField'
import { useSettings, useUpdateSettings } from '../../hooks/useApi'
import { ValidationError } from '../../api/errors'
import { TIMEZONE_CHOSEN_KEY } from '../../lib/timezone'

vi.mock('../../hooks/useApi', () => ({
  useSettings: vi.fn(),
  useUpdateSettings: vi.fn(),
}))

type Callbacks = { onSuccess?: () => void; onError?: (e: Error) => void }
const mutate = vi.fn()

beforeEach(() => {
  localStorage.clear()
  mutate.mockReset()
  vi.mocked(useSettings).mockReturnValue({
    data: { timezone: 'UTC' },
    isLoading: false,
  } as never)
  vi.mocked(useUpdateSettings).mockReturnValue({ mutate, isPending: false } as never)
})

describe('TimeZoneField', () => {
  it('shows the current value and saves a new zone, remembering the manual choice', async () => {
    const user = userEvent.setup()
    mutate.mockImplementation((_u: unknown, cb: Callbacks) => cb.onSuccess?.())
    render(<TimeZoneField />)
    const input = screen.getByLabelText('Time zone')
    expect(input).toHaveValue('UTC')
    expect(screen.getByRole('button', { name: 'Save time zone' })).toBeDisabled()

    await user.clear(input)
    await user.type(input, 'Asia/Tokyo')
    await user.click(screen.getByRole('button', { name: 'Save time zone' }))

    expect(mutate).toHaveBeenCalledWith({ timezone: 'Asia/Tokyo' }, expect.any(Object))
    expect(localStorage.getItem(TIMEZONE_CHOSEN_KEY)).toBe('1')
  })

  it('shows the server field error on a 422 and does not mark it chosen', async () => {
    const user = userEvent.setup()
    mutate.mockImplementation((_u: unknown, cb: Callbacks) => {
      const err = new ValidationError('Invalid', 422)
      err.fields = { timezone: 'Unknown time zone' }
      cb.onError?.(err)
    })
    render(<TimeZoneField />)
    const input = screen.getByLabelText('Time zone')
    await user.clear(input)
    await user.type(input, 'Mars/Base')
    await user.click(screen.getByRole('button', { name: 'Save time zone' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Unknown time zone')
    expect(localStorage.getItem(TIMEZONE_CHOSEN_KEY)).toBeNull()
  })

  it('disables the field while settings load', () => {
    vi.mocked(useSettings).mockReturnValue({ data: undefined, isLoading: true } as never)
    render(<TimeZoneField />)
    expect(screen.getByLabelText('Time zone')).toBeDisabled()
  })
})
