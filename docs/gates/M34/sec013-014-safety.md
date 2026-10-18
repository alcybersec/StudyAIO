# M34-S2-SEC-013 and M34-S2-SEC-014: safety review of the held build

**Reviewer:** `safety` (veto role) · **Date:** 2026-10-16
**Subject:** three held commits, cherry-picked onto `kit/retrofit` @ `e5245c8` with no conflicts:

| Held | On this branch | Commit |
|---|---|---|
| `d766b8c` | `5fcebe7` | test(red): OAuth tokens not stored and hashed Telegram pairing codes |
| `c597a77` | `21e8223` | data: revision `c3e5a7b9d1f2` (nulls OAuth tokens; nulls `link_token` in both directions) |
| `31bcb3a` | `95d0518` | backend: no token stored, no `access_type=offline`, digest lookup for the pairing code |

Reviewed against floors 2 and 4, `docs/gates/M34/contracts-safety.md` R1 and R3, and the contract entries
`models.secrets-at-rest v2` and `models.telegram-pairing-code v1`.

## Verdict: **APPROVE**

Floors 1-4 hold on the code as written. Nothing writes a provider token any more, the pairing code is a digest at
rest and in the lookup, neither is logged, and the revision deletes nothing. No finding blocks; section 5 lists
residuals.

## 1. Floor tier on the build before this change

`tests/safety` on the cherry-picked tree: **740 passed, 1 skipped**, no red. The existing classification of
`telegram_links.link_token` ("plaintext pairing code, hashing is a follow-up") was stale but did not fail,
because the scan only checks that each credential-named column is classified. Updated below.

## 2. Pins added

All in `services/app/tests/safety/test_floor2_tokens_at_rest.py`, mapped in `FLOORS.md`.

- **Classification.** `telegram_links.link_token` stays in `NOT_ENCRYPTED_REVIEWED`, reason now "SHA-256 digest
  of our own one-time pairing code". The two `oauth_accounts` columns stay in `MUST_ENCRYPT` until v3 (section 3).
- **No path writes a non-`None` OAuth token.** Signature (no token parameter, no `**kwargs`); a static scan of every
  `app/` module touching `OAuthAccount` for constructor keywords, attribute writes, `setattr` and `.values(...)`,
  with a non-vacuity check on the two `None` sweeps; the real service over MiniDB on both branches, the
  known-identity one seeded with a deploy-window token; the callback driven end to end with sentinel tokens,
  success and service failure, under the real logging chain (the token reaches `fetch_userinfo` and nothing else,
  and never the log or the redirect); Google's authorize URL without `access_type`.
- **Pairing code.** Over MiniDB with a second user's pending code: create and regenerate store only the SHA-256;
  the plaintext is nowhere in any row; an old code and the stored digest both miss; the lookup binds the digest,
  not the code; a hit consumes the code and leaves the other user's row alone; the code and digest never reach the
  log, from the service or from `/start` (hit, digest, unknown). A static check that no `logger.*` call in
  `telegram_service` or `api/notifications.py` passes the code, its digest or the update text.
- **Revision `c3e5a7b9d1f2`** on SQLite: upgrade deletes no row, keeps the identity and link columns, nulls tokens
  and pending codes, prints no value, and is idempotent; downgrade leaves `oauth_accounts` exactly as it is (a
  straggler value included), nulls every digest, keeps linked chats, prints no value, and the docstring says the
  tokens cannot be restored.
- **Not pinned:** pairing codes never expire (R-048, open).

### Mutation check

21 mutations, applied one at a time to a scratch copy of `services/app/` outside the worktree, each running only
the new pins (baseline 16 passed): **21/21 killed**. The deploy-window sweep removed; a token written on the
known-identity branch; a token on the new `OAuthAccount`; the parameter back and passed by the callback;
`**kwargs`; the callback logging the token on success, and on failure; `access_type=offline` back; plaintext stored
on create, and on regenerate; plaintext lookup; a lookup that also accepts the digest; the code logged on generate;
`/start` text logged; the code not consumed; the upgrade deleting OAuth rows; leaving pending codes; deleting
pending Telegram rows; printing a token; the downgrade leaving digests; the docstring warning removed. The first
"prints a token" mutation was placed after the `UPDATE` and so printed `NULL`s (equivalent); moved before it, red.

## 3. Floor 2

- **Writers.** At `95d0518` the only writes of `OAuthAccount.access_token`/`refresh_token` in `app/` are the two
  `None` sweeps in `create_or_link_oauth`; the link branch constructs `OAuthAccount` without them; `oauth_callback`
  passes neither. Nothing reads them (rotation list and export exclusion only). The token dict stays a local of the
  callback, passed only to `fetch_userinfo`. `logger.exception("oauth_callback_failed")` would render an exception
  carrying a token only if `fetch_userinfo` raised one with the token in its text; `hide_parameters=True` covers DB
  errors, and the logging backstop covers `[parameters: ...]`. No change from SEC-005 there.
- **Pairing code.** `hash_magic_link_token` is the existing SHA-256 helper (no second digest function). The code
  is a 256-bit `token_urlsafe(32)`, so a fast hash is right. Comparison happens in SQL; nothing compares in Python.
  The plaintext lives in the `TelegramLinkResponse` to its own user only (floor 1 unchanged: `generate_link_token`
  is keyed on the caller's `user.id`). The model docstring still says nothing about the digest (contract: "the
  model's docstring says the column holds a digest") — documentation only, for `data`; not blocking.

## 4. Floor 4, the deploy window, and the downgrade

- **Floor 4.** Provider tokens are credentials the product never used after sign-in, not uploads or generated
  content; nulling them loses no user data (R1). Pending pairing codes are one-click regenerable. The revision is a
  Core `UPDATE` in both tables; no `DELETE`, no other column touched; every linked chat (`verified`, `chat_id`,
  `username`) survives. Pinned.
- **Why keep the columns one release.** `infra/deploy/deploy.sh` migrates in a one-off container while the old api
  keeps serving and states that it "relies on migrations being additive/backwards-compatible for one release".
  The old api's ORM selects every mapped column of `oauth_accounts` on each OAuth sign-in; dropped columns would
  fail those sign-ins in the window. Keeping them nullable, always NULL and still `EncryptedText` costs nothing and
  means a straggler write by the old api is ciphertext, which the new code then sweeps on that user's next sign-in.
  Sound. v3 must drop the two columns, the two `RAW_SECRET_COLUMNS` entries and the two `MUST_ENCRYPT` entries
  together, as the contract says.
- **Downgrade, OAuth.** A no-op is the only honest choice: the values are gone and no older release reads them
  (they were never read after login). The docstring says "cannot be restored". Accepted.
- **Downgrade, Telegram.** Nulling the digests is required, not optional: the older code compares the presented
  code as plaintext, so a digest left in place becomes a usable code for anyone holding a post-upgrade dump.
  Correct as implemented and pinned.
- **Deploy window, Telegram.** Old api, new schema: plaintext codes it writes never match the new digest lookup
  (inert; the downgrade nulls them). New api, old verifier still serving: a digest presented to the old api would
  match, but only to someone reading the database during the window. Accepted residual.

## 5. Residuals and non-blocking findings

1. Already-issued provider tokens remain valid at Google/GitHub until expiry or revocation (sign-in scopes only).
   Accepted in the contract (v2 item 7).
2. R-048: pairing codes never expire. Open, owner `backend`/`data`.
3. `TelegramLink` docstring not updated to say the column is a digest (`data`, documentation).
4. Pre-existing, not floor 2 after SEC-014: the Telegram webhook's header check compares against
   `telegram_webhook_url` (a URL derivable from the public host) with `!=`. Recommend a random
   `TELEGRAM_WEBHOOK_SECRET` registered via `setWebhook(secret_token=...)` and `hmac.compare_digest`. Candidate
   risk-register row for the Orchestrator.
5. `tests/integration/test_oauth_flow.py:258` still asserts `access_type=offline`; `qa`'s, being fixed in parallel.

Threat model: assets rows and B6 updated, delta in §5 "2026-10-16, M34 S2 (M34-S2-SEC-013, M34-S2-SEC-014)".
