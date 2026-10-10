import { renderHook } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useAutoTimeZone } from './useUserTimeZone'
import { useSettings, useUpdateSettings } from './useApi'
import { TIMEZONE_CHOSEN_KEY } from '../lib/timezone'

vi.mock('./useApi', () => ({
  useSettings: vi.fn(),
  useUpdateSettings: vi.fn(),
}))

const mutate = vi.fn()

function stored(timezone: string | undefined) {
  vi.mocked(useSettings).mockReturnValue({
    data: timezone === undefined ? undefined : { timezone },
  } as never)
}

function browserZone(zone: string) {
  vi.spyOn(Intl.DateTimeFormat.prototype, 'resolvedOptions').mockReturnValue({
    timeZone: zone,
  } as Intl.ResolvedDateTimeFormatOptions)
}

beforeEach(() => {
  vi.restoreAllMocks()
  localStorage.clear()
  mutate.mockReset()
  vi.mocked(useUpdateSettings).mockReturnValue({ mutate } as never)
})

describe('useAutoTimeZone', () => {
  it('sets the browser zone once when the stored zone is the default', () => {
    stored('UTC')
    browserZone('Europe/Berlin')
    const { rerender } = renderHook(() => useAutoTimeZone())
    rerender()
    rerender()
    expect(mutate).toHaveBeenCalledTimes(1)
    expect(mutate).toHaveBeenCalledWith({ timezone: 'Europe/Berlin' })
  })

  it('does not override a stored non-default zone', () => {
    stored('Asia/Tokyo')
    browserZone('Europe/Berlin')
    renderHook(() => useAutoTimeZone())
    expect(mutate).not.toHaveBeenCalled()
  })

  it('does not override a manual choice of UTC', () => {
    localStorage.setItem(TIMEZONE_CHOSEN_KEY, '1')
    stored('UTC')
    browserZone('Europe/Berlin')
    renderHook(() => useAutoTimeZone())
    expect(mutate).not.toHaveBeenCalled()
  })

  it('waits for settings to load, then acts once', () => {
    stored(undefined)
    browserZone('Europe/Berlin')
    const { rerender } = renderHook(() => useAutoTimeZone())
    expect(mutate).not.toHaveBeenCalled()
    stored('UTC')
    rerender()
    expect(mutate).toHaveBeenCalledTimes(1)
  })

  it('does nothing when the browser is also on UTC', () => {
    stored('UTC')
    browserZone('UTC')
    renderHook(() => useAutoTimeZone())
    expect(mutate).not.toHaveBeenCalled()
  })
})
