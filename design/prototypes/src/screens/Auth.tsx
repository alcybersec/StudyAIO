import { Clock } from 'lucide-react'
import { Button, Input, Card } from '../ui'

/**
 * Redesigned login. Centered auth card on surface-0 (no PageShell).
 * The password field demonstrates the 401 mapping ("wrong password, N attempts
 * left"); the second card below demonstrates the 429 rate-limited state —
 * two different failures, two clearly different treatments.
 */
export function Auth() {
  return (
    <div className="min-h-full flex flex-col items-center justify-center py-16 px-6 bg-surface-0">
      <Card className="w-full max-w-sm p-6">
        {/* logo + wordmark */}
        <div className="flex flex-col items-center text-center mb-6">
          <div
            className="w-10 h-10 rounded-xl bg-sage text-on-accent flex items-center justify-center font-bold text-lg"
            aria-hidden
          >
            S
          </div>
          <h1 className="text-lg font-bold tracking-tight mt-3">StudyAIO</h1>
          <p className="text-xs text-text-muted mt-0.5">Your lecture-to-exam pipeline</p>
        </div>

        <form className="space-y-4" onSubmit={(e) => e.preventDefault()}>
          <Input id="auth-email" label="Email" type="email" defaultValue="alex@example.com" autoComplete="email" />

          {/* 401 mapping demo: specific, human, tells you the consequence */}
          <Input
            id="auth-password"
            label="Password"
            type="password"
            defaultValue="••••••••"
            autoComplete="current-password"
            error="Wrong password — 2 attempts before a 5-minute cooldown"
          />

          <Button type="submit" className="w-full" size="lg">
            Sign in
          </Button>
        </form>

        {/* divider */}
        <div className="flex items-center gap-3 my-5" aria-hidden>
          <span className="h-px flex-1 bg-border" />
          <span className="text-[11px] text-text-faint">or</span>
          <span className="h-px flex-1 bg-border" />
        </div>

        <div className="space-y-2">
          <Button variant="secondary" className="w-full">
            Continue with Google
          </Button>
          <Button variant="secondary" className="w-full">
            Continue with GitHub
          </Button>
        </div>

        <p className="text-xs text-text-muted text-center mt-6">
          <a href="#" className="hover:text-text underline-offset-2 hover:underline">
            Create account
          </a>
          <span className="text-text-faint mx-1.5">·</span>
          <a href="#" className="hover:text-text underline-offset-2 hover:underline">
            Forgot password?
          </a>
        </p>
      </Card>

      {/* 429 rate-limited state demo — distinct from a wrong password */}
      <Card dense className="w-full max-w-sm mt-4 bg-amber-soft! border-amber/25!">
        <div role="status" className="flex items-center gap-2.5 text-xs text-amber-fg font-medium">
          <Clock size={14} aria-hidden />
          <span>Too many attempts — try again in</span>
          <span className="ml-auto font-mono text-[13px] font-semibold tabular-nums">4:32</span>
        </div>
      </Card>
    </div>
  )
}
