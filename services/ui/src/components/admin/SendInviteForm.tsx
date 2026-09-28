import { useState } from 'react'
import { Mail } from 'lucide-react'
import { toast } from 'sonner'
import { Button, Input } from '../ui'
import { useSendInvite } from '../../hooks/useApi'
import { InviteLinkNotice } from './InviteLinkNotice'
import type { InviteSendResult } from '../../types'

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
        <div className="mt-3">
          <InviteLinkNotice result={result} />
        </div>
      )}
    </div>
  )
}
