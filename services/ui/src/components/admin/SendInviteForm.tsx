import { useState } from 'react'
import { Check, Copy, Mail, TriangleAlert } from 'lucide-react'
import { toast } from 'sonner'
import { Button, Input } from '../ui'
import { useSendInvite } from '../../hooks/useApi'
import type { InviteSendResult } from '../../types'

interface CopyLinkProps {
  url: string
}

function CopyLink({ url }: CopyLinkProps) {
  const [copied, setCopied] = useState(false)

  return (
    <button
      type="button"
      className="inline-flex max-w-full items-center gap-1.5 font-mono text-[11px] text-text hover:text-sage-fg transition-colors"
      onClick={() => {
        void navigator.clipboard
          .writeText(url)
          .then(() => {
            setCopied(true)
            setTimeout(() => setCopied(false), 1500)
          })
          .catch(() => toast.error('Could not copy to clipboard'))
      }}
      aria-label="Copy invite link"
    >
      <span className="truncate">{url}</span>
      {copied ? (
        <Check size={12} className="shrink-0" aria-hidden />
      ) : (
        <Copy size={12} className="shrink-0" aria-hidden />
      )}
    </button>
  )
}

/**
 * Email a single-use invite to one person.
 *
 * The link is shown after sending whether or not delivery succeeded. An
 * instance with broken SMTP must not become one where nobody can be onboarded —
 * the admin copies the link and passes it on. It is also the only time the
 * token is ever visible: the server stores only its hash.
 */
export function SendInviteForm() {
  const [email, setEmail] = useState('')
  const [note, setNote] = useState('')
  const [expiryDays, setExpiryDays] = useState('14')
  const [result, setResult] = useState<InviteSendResult | null>(null)

  const sendInvite = useSendInvite()
  const trimmed = email.trim()

  return (
    <div className="border-b border-border p-4">
      <div className="flex flex-wrap items-end gap-3">
        <Input
          id="invite-email"
          label="Invite by email"
          type="email"
          placeholder="tester@example.com"
          className="w-56"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
        <Input
          id="invite-email-note"
          label="Message (optional)"
          placeholder="Added to the email"
          className="w-48"
          value={note}
          onChange={(e) => setNote(e.target.value)}
        />
        <Input
          id="invite-email-expiry"
          label="Expires in (days)"
          type="number"
          min={1}
          className="w-32"
          value={expiryDays}
          onChange={(e) => setExpiryDays(e.target.value)}
        />
        <Button
          size="sm"
          disabled={sendInvite.isPending || trimmed === ''}
          onClick={() =>
            sendInvite.mutate(
              {
                email: trimmed,
                note: note.trim() || undefined,
                expires_in_days: Number(expiryDays) || null,
              },
              {
                onSuccess: (sent) => {
                  setResult(sent)
                  setEmail('')
                  setNote('')
                  if (sent.email_sent) toast.success(`Invite sent to ${sent.invite.email}`)
                  else toast.warning('Invite created, but the email could not be sent')
                },
                onError: () => toast.error("Couldn't create the invite"),
              },
            )
          }
        >
          <Mail size={12} aria-hidden />
          {sendInvite.isPending ? 'Sending…' : 'Send invite'}
        </Button>
      </div>

      {result && (
        <div className="mt-3 rounded-lg border border-border bg-surface-2 p-3">
          {!result.email_sent && (
            <p className="mb-1.5 flex items-center gap-1.5 text-[11px] text-amber-fg">
              <TriangleAlert size={12} aria-hidden />
              The email could not be sent. Pass this link on yourself.
            </p>
          )}
          <p className="mb-1 text-[11px] text-text-faint">
            Invite link for {result.invite.email} — shown once, single use.
          </p>
          <CopyLink url={result.invite_url} />
        </div>
      )}
    </div>
  )
}
