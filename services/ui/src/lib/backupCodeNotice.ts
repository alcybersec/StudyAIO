/**
 * Carries "you have N backup codes left" from the sign-in that spent one to
 * the app shell that can actually show it.
 *
 * The count arrives on the login response and nowhere else — the API reports
 * it once, on the login that consumed a code, and deliberately does not expose
 * it as pollable account state. But the login page cannot display it: the
 * moment the session is established `PublicOnlyRoute` redirects off `/login`,
 * so anything rendered there is unmounted in the same tick. Nor can the login
 * page raise a toast, because `<Toaster />` is mounted inside `AppLayout` and
 * sonner drops a toast published while nothing is subscribed.
 *
 * So the count is parked here and picked up by `<BackupCodeNotice />` once the
 * app shell mounts. A module-level variable is enough and is deliberate: the
 * hop is a client-side route change within one JS context, and the value is
 * strictly single-use — a stale count surviving into a later session (which is
 * what `sessionStorage` would risk) would be worse than showing nothing.
 */
let pendingRemaining: number | null = null

/** Record the count reported by a sign-in that spent a backup code. */
export function rememberBackupCodesRemaining(remaining: number): void {
  pendingRemaining = remaining
}

/**
 * Read and clear the parked count. Returns null when no backup code was spent.
 * `0` is a real, meaningful value here — the user has just used their last
 * code — so callers must compare against null rather than test truthiness.
 */
export function takeBackupCodesRemaining(): number | null {
  const remaining = pendingRemaining
  pendingRemaining = null
  return remaining
}
