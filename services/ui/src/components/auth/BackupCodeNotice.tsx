import { useEffect } from 'react'
import i18n from '../../i18n'
import { toast } from 'sonner'
import { takeBackupCodesRemaining } from '../../lib/backupCodeNotice'

/**
 * Tells the user how many MFA backup codes they have left, once, immediately
 * after a sign-in that spent one.
 *
 * Renders nothing. It exists to be mounted inside `AppLayout` — alongside the
 * `<Toaster />` that can actually display the toast — because the login page
 * itself is redirected away the instant the session is established. See
 * `lib/backupCodeNotice.ts` for why the count has to travel to get here.
 */
export function BackupCodeNotice() {

  useEffect(() => {
    const remaining = takeBackupCodesRemaining()
    // `0` is a real value: the user just burned their last code and that is
    // precisely when they most need telling. Never `if (!remaining)`.
    if (remaining === null) return

    if (remaining === 0) {
      toast.warning(i18n.t(i18n.t('That was your last backup code')), {
        description:
          i18n.t('You have no backup codes left. Set up two-factor authentication again in Settings to get a new set.'),
        duration: 10000,
      })
      return
    }

    toast.info(`Signed in with a backup code — ${remaining} left`, {
      description:
        remaining <= 2
          ? i18n.t('Set up two-factor authentication again in Settings to get a fresh set.')
          : i18n.t('Each code works once. Cross this one off your list.'),
      duration: 8000,
    })
  }, [])

  return null
}
