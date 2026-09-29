import { useState } from 'react'
import i18n from '../../i18n'
import { useTranslation } from 'react-i18next'
import { Check, Copy, Plus, Send } from 'lucide-react'
import { toast } from 'sonner'
import { Badge, Button, ErrorState, Input, Table, TBody, TCell, THead, TRow } from '../ui'
import {
  useCreateInvite,
  useInvites,
  useResendInvite,
  useRevokeInvite,
} from '../../hooks/useApi'
import { InviteLinkNotice } from './InviteLinkNotice'
import { SendInviteForm } from './SendInviteForm'
import type { InviteCode, InviteSendResult } from '../../types'

/**
 * Whether Resend applies. Only email invites have somewhere to send to, and a
 * revoked or already-accepted one is deliberately excluded — see
 * `invite_service.resend_email_invite`. An expired invite IS resendable: that
 * is the usual reason to reach for the button.
 */
function canResend(invite: InviteCode): boolean {
  return (
    invite.email !== null && invite.revoked_at === null && invite.used_count < invite.max_uses
  )
}

/** Why a code can't be redeemed — shown instead of a bare "no". */
function inviteStatus(invite: InviteCode): { label: string; variant: 'success' | 'default' } {
  if (invite.revoked_at) return { label: 'revoked', variant: 'default' }
  if (invite.expires_at && new Date(invite.expires_at) < new Date()) {
    return { label: 'expired', variant: 'default' }
  }
  if (invite.uses_remaining === 0) return { label: 'used up', variant: 'default' }
  return { label: 'active', variant: 'success' }
}

function CopyButton({ code }: { code: string }) {
  const { t } = useTranslation()
  const [copied, setCopied] = useState(false)

  return (
    <button
      type="button"
      className="inline-flex items-center gap-1.5 font-mono text-xs text-text hover:text-sage-fg transition-colors"
      onClick={() => {
        void navigator.clipboard
          .writeText(code)
          .then(() => {
            setCopied(true)
            setTimeout(() => setCopied(false), 1500)
          })
          .catch(() => toast.error(i18n.t('Could not copy to clipboard')))
      }}
      aria-label={t('Copy invite code {{code}}', { code })}
    >
      {code}
      {copied ? <Check size={12} aria-hidden /> : <Copy size={12} aria-hidden />}
    </button>
  )
}

/** Issue and revoke registration invite codes. Admin-only. */
export function InvitePanel() {
  const { t } = useTranslation()

  const [note, setNote] = useState('')
  const [maxUses, setMaxUses] = useState('1')
  const [expiryDays, setExpiryDays] = useState('30')

  const { data, isLoading, isError, refetch } = useInvites()

  const createInvite = useCreateInvite()
  const revokeInvite = useRevokeInvite()
  const resendInvite = useResendInvite()
  // Resending rotates the token, so the new link is only ever visible here.
  const [resent, setResent] = useState<InviteSendResult | null>(null)

  return (
    <div className="bg-surface-1 rounded-xl border border-border">
      <div className="flex flex-wrap items-center gap-3 p-4 border-b border-border">
        <h2 className="text-sm font-semibold text-text">{t('Invite codes')}</h2>
        <span className="text-[11px] text-text-faint">
          {t('Required to register when REGISTRATION_MODE=invite')}
        </span>
      </div>

      <SendInviteForm />

      <div className="flex flex-wrap items-end gap-3 p-4 border-b border-border">
        <Input
          id="invite-note"
          label={t('Note')}
          placeholder={t('Who is this for?')}
          className="w-48"
          value={note}
          onChange={(e) => setNote(e.target.value)}
        />
        <Input
          id="invite-max-uses"
          label={t('Max uses')}
          type="number"
          min={1}
          className="w-24"
          value={maxUses}
          onChange={(e) => setMaxUses(e.target.value)}
        />
        <Input
          id="invite-expiry"
          label={t('Expires in (days)')}
          type="number"
          min={1}
          className="w-32"
          value={expiryDays}
          onChange={(e) => setExpiryDays(e.target.value)}
        />
        <Button
          size="sm"
          disabled={createInvite.isPending}
          onClick={() =>
            createInvite.mutate(
              {
                note: note.trim() || undefined,
                max_uses: Number(maxUses) || 1,
                expires_in_days: Number(expiryDays) || null,
              },
              {
                onSuccess: (invite) => {
                  setNote('')
                  toast.success(i18n.t('Created {{code}}', { code: invite.code }))
                },
                onError: () => toast.error(i18n.t("Couldn't create the invite code")),
              },
            )
          }
        >
          <Plus size={12} aria-hidden />
          {createInvite.isPending ? t('Creating…') : t('Create invite')}
        </Button>
      </div>

      {resent && (
        <div className="px-4 pt-3">
          <InviteLinkNotice result={resent} />
        </div>
      )}

      {isLoading && !data ? (
        <p className="p-4 text-xs text-text-muted">{t('Loading invite codes…')}</p>
      ) : isError && !data ? (
        <div className="p-4">
          <ErrorState compact title={t("Invite codes couldn't load")} onRetry={() => void refetch()} />
        </div>
      ) : data && data.invites.length > 0 ? (
        <div className="px-4 pb-2">
          <Table>
            <THead>
              <TCell header>{t('Code')}</TCell>
              <TCell header>{t('Sent to')}</TCell>
              <TCell header>{t('Note')}</TCell>
              <TCell header>{t('Uses')}</TCell>
              <TCell header>{t('Accepted')}</TCell>
              <TCell header>{t('Status')}</TCell>
              <TCell header>{t('Expires')}</TCell>
              <TCell header />
            </THead>
            <TBody>
              {data.invites.map((invite) => {
                const status = inviteStatus(invite)
                return (
                  <TRow key={invite.id}>
                    <TCell>
                      <CopyButton code={invite.code} />
                    </TCell>
                    <TCell>
                      {invite.email ? (
                        <span className="text-xs text-text-muted">
                          {invite.email}
                          {/* Created but never delivered: an SMTP problem, not
                              a disinterested tester. Worth distinguishing. */}
                          {!invite.sent_at && (
                            <span className="ml-1 text-[10px] text-amber-fg">{t('not sent')}</span>
                          )}
                        </span>
                      ) : (
                        <span className="text-xs text-text-faint">{t('shared code')}</span>
                      )}
                    </TCell>
                    <TCell>
                      <span className="text-xs text-text-muted">{invite.note ?? '—'}</span>
                    </TCell>
                    <TCell>
                      <span className="text-xs font-mono text-text-muted">
                        {invite.used_count}/{invite.max_uses}
                      </span>
                    </TCell>
                    <TCell>
                      <span className="text-xs text-text-faint">
                        {invite.accepted_at
                          ? new Date(invite.accepted_at).toLocaleDateString()
                          : '—'}
                      </span>
                    </TCell>
                    <TCell>
                      <Badge variant={status.variant}>{t(status.label)}</Badge>
                    </TCell>
                    <TCell>
                      <span className="text-xs text-text-faint">
                        {invite.expires_at
                          ? new Date(invite.expires_at).toLocaleDateString()
                          : t('never')}
                      </span>
                    </TCell>
                    <TCell>
                      <div className="flex items-center gap-1">
                        {canResend(invite) && (
                          <Button
                            variant="ghost"
                            size="sm"
                            disabled={resendInvite.isPending}
                            onClick={() =>
                              resendInvite.mutate(
                                { inviteId: invite.id },
                                {
                                  onSuccess: (sent) => {
                                    setResent(sent)
                                    if (sent.email_sent) {
                                      toast.success(i18n.t('Invite resent to {{email}}', { email: sent.invite.email }))
                                    } else {
                                      toast.warning(
                                        i18n.t('Invite reissued, but the email could not be sent'),
                                      )
                                    }
                                  },
                                  onError: () => toast.error(i18n.t("Couldn't resend the invite")),
                                },
                              )
                            }
                          >
                            <Send size={12} aria-hidden />
                            {t('Resend')}
                          </Button>
                        )}
                        {!invite.revoked_at && (
                          <Button
                            variant="ghost"
                            size="sm"
                            disabled={revokeInvite.isPending}
                            onClick={() =>
                              revokeInvite.mutate(invite.id, {
                                onSuccess: () => toast.success(i18n.t('Invite revoked')),
                                onError: () => toast.error(i18n.t("Couldn't revoke the invite code")),
                              })
                            }
                          >
                            {t('Revoke')}
                          </Button>
                        )}
                      </div>
                    </TCell>
                  </TRow>
                )
              })}
            </TBody>
          </Table>
        </div>
      ) : (
        <p className="p-4 text-xs text-text-muted">
          {t('No invite codes yet. Create one to let a tester sign up.')}
        </p>
      )}
    </div>
  )
}
