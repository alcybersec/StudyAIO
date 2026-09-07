import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render } from '@testing-library/react'
import { rememberBackupCodesRemaining, takeBackupCodesRemaining } from '../../lib/backupCodeNotice'
import { BackupCodeNotice } from './BackupCodeNotice'

const toastInfo = vi.fn()
const toastWarning = vi.fn()

vi.mock('sonner', () => ({
  toast: {
    info: (...args: unknown[]) => toastInfo(...args),
    warning: (...args: unknown[]) => toastWarning(...args),
  },
}))

describe('BackupCodeNotice', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    takeBackupCodesRemaining()
  })

  it('says nothing when no backup code was spent', () => {
    render(<BackupCodeNotice />)

    expect(toastInfo).not.toHaveBeenCalled()
    expect(toastWarning).not.toHaveBeenCalled()
  })

  it('reports how many codes are left', () => {
    rememberBackupCodesRemaining(5)
    render(<BackupCodeNotice />)

    expect(toastInfo).toHaveBeenCalledWith(
      expect.stringContaining('5'),
      expect.anything(),
    )
  })

  it('warns loudly when the last code has just been spent', () => {
    // `0` is a real count, not "nothing to report". A truthiness check here
    // would stay silent at exactly the moment the user most needs telling.
    rememberBackupCodesRemaining(0)
    render(<BackupCodeNotice />)

    expect(toastWarning).toHaveBeenCalledWith(
      expect.stringContaining('last backup code'),
      expect.anything(),
    )
    expect(toastInfo).not.toHaveBeenCalled()
  })

  it('reports only once, so a later navigation does not repeat it', () => {
    rememberBackupCodesRemaining(4)
    const first = render(<BackupCodeNotice />)
    expect(toastInfo).toHaveBeenCalledTimes(1)

    first.unmount()
    render(<BackupCodeNotice />)

    expect(toastInfo).toHaveBeenCalledTimes(1)
  })
})
