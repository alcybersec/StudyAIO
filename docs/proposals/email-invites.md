# Email invites

**Status:** proposal, nothing built. Written 2026-09-28.
**Size:** S–M, about a day.
**Depends on:** SMTP (already configured in production), `REGISTRATION_MODE=invite` (already live).

## The problem this actually solves

Invites today are codes an admin creates and passes on out of band. That works,
but it makes one number on the beta funnel much weaker than it looks.

`invites_issued` counts **capacity** — "five uses outstanding". It cannot say how
many *people* were invited, or which of them never opened the link. So when the
funnel shows a gap between invited and registered, there is no way to tell
whether the invites were never sent, never opened, or opened and abandoned.

Per-person email invites turn `invited → registered` into a real conversion rate
with names attached. Three testers who never clicked is a completely different
problem from three who registered and never uploaded, and today those are
indistinguishable.

That is the argument for this feature. The convenience of not copy-pasting a code
is secondary.

## The design choice

**(a) The link prefills the existing code** — `/register?invite=BETA-7F3KQ2MN`.
An afternoon's work, reuses everything untouched. But the code remains a shared
secret: forwardable, and acceptance is untrackable.

**(b) A per-invitation token bound to one email address.** The admin types an
address; the app sends a link only that person can use.

**Recommendation: (b).** It is barely more work and it is the half that feeds the
funnel. Shared codes stay for the case they are genuinely good at — one link
pasted into a group chat.

## Schema

Extend `invite_codes` rather than adding a table. It already carries `max_uses`,
`used_count`, `expires_at`, `revoked_at`, `created_by` and `note`, and
`users.invite_code_id` already records which invite an account used.

| Column | Type | Why |
|---|---|---|
| `email` | `String(255)`, nullable | Who it was sent to. Null for shared codes |
| `token_hash` | `String(64)`, unique, indexed | SHA-256. **Never the raw token** |
| `sent_at` | `DateTime`, nullable | Distinguishes "created" from "actually emailed" |
| `accepted_at` | `DateTime`, nullable | The funnel number that does not exist today |

`token_hash` follows `magic_links` exactly. That pattern was hardened in S.1
(issue #11) — hashed at rest, single-use, expiring — and there is no reason to
invent a second one.

## Backend

- `invite_service.create_email_invite(email, note, expires_in)` — mints a token,
  stores only its hash, returns the raw value once to the caller.
- `invite_service.redeem_token(token)` — hashes, looks up, reuses the existing
  `SELECT … FOR UPDATE` so two simultaneous sign-ups cannot both spend the last
  use, and returns an **identical error** for unknown, spent, expired and revoked.
  A guesser learns nothing. `redeem_invite` already does this for codes.
- `POST /api/admin/invites/send` — creates, emails, records `sent_at`. **Returns
  the link whether or not the email went out**, mirroring `AddUserForm`'s setup
  link: a beta instance with broken SMTP must not become an instance where nobody
  can be onboarded.
- `POST /api/auth/register` accepts `?invite=<token>` alongside the existing code
  field.

## Email

A new `invite.html` extending `templates/base.html`, sent through
`email_service.send_templated_email`. SMTP and `APP_BASE_URL` are already
configured in production, so this adds no infrastructure.

## Frontend

A "Send invite" form beside the existing `InvitePanel`, and the invite list
gaining email / sent / accepted columns. `RegisterPage` reads `?invite=` into the
field it already has — the token replaces typing a code, so the page barely
changes.

## The security line

**The link is a bearer credential, exactly like a password reset.** The repo
already has rules for these and this must follow them rather than re-derive them:

- hashed at rest (`token_hash`, never the raw value in the database)
- `?token=` stripped from Sentry URLs by `observability.scrub_event`
- never written to the structured log in SaaS mode
- single-use and expiring

## One decision left open

**Should an email invite be strictly single-use (`max_uses = 1`)?**

Recommended yes — it is what makes `accepted_at` mean anything. The cost is that
a tester who loses the email needs a resend, so the admin panel needs that button.

## Tests worth writing

- An invite for one email cannot be redeemed twice.
- The rejection error is byte-identical across unknown, spent, expired and
  revoked — the guard that already exists for codes.
- `sent_at` and `accepted_at` move independently.
- An SMTP failure still returns a usable link.
- The raw token never appears in a log line or in the list response.
