import { useState } from 'react'
import { Check, Copy, TriangleAlert } from 'lucide-react'
import { toast } from 'sonner'
import type { InviteSendResult } from '../../types'

interface InviteLinkNoticeProps {
  result: InviteSendResult
}

/**
 * The invite link, shown after sending or resending.
 *
 * Shared by both actions because both have the same failure mode: an instance
 * with broken SMTP must not become one where nobody can be onboarded. The link
 * is displayed whether or not delivery succeeded, and this is the only time it
 * is ever visible — the server stores only its hash.
 */
export function InviteLinkNotice({ result }: InviteLinkNoticeProps) {
  const [copied, setCopied] = useState(false)

  return (
    <div className="rounded-lg border border-border bg-surface-2 p-3">
      {!result.email_sent && (
        <p className="mb-1.5 flex items-center gap-1.5 text-[11px] text-amber-fg">
          <TriangleAlert size={12} aria-hidden />
          The email could not be sent. Pass this link on yourself.
        </p>
      )}
      <p className="mb-1 text-[11px] text-text-faint">
        Invite link for {result.invite.email} — shown once, single use.
      </p>
      <button
        type="button"
        className="inline-flex max-w-full items-center gap-1.5 font-mono text-[11px] text-text hover:text-sage-fg transition-colors"
        onClick={() => {
          void navigator.clipboard
            .writeText(result.invite_url)
            .then(() => {
              setCopied(true)
              setTimeout(() => setCopied(false), 1500)
            })
            .catch(() => toast.error('Could not copy to clipboard'))
        }}
        aria-label="Copy invite link"
      >
        <span className="truncate">{result.invite_url}</span>
        {copied ? (
          <Check size={12} className="shrink-0" aria-hidden />
        ) : (
          <Copy size={12} className="shrink-0" aria-hidden />
        )}
      </button>
    </div>
  )
}
