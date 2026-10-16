# M34-S2-SEC-015: safety review of the held build (Telegram webhook authenticity, R-052)

**Reviewer:** `safety` (veto role) · **Date:** 2026-10-16
**Subject:** two held commits, cherry-picked onto `kit/retrofit` @ `3f5e3ac` with no conflicts:

| Held | On the review branch | Commit |
|---|---|---|
| `12358b5` | `7197da5` | test(red): the webhook checks a dedicated secret in constant time and fails closed |
| `b08c589` | `373ad11` | fix(api): `TELEGRAM_WEBHOOK_SECRET` (`SecretStr`), `hmac.compare_digest`, fail closed in multi-user, `telegram_service.register_webhook`, CLI `register-telegram-webhook` |

Reviewed against floors 1 and 2 and the threat-model residual SEC-013/014 §5 item 7(d), which raised R-052.

## Verdict: **APPROVE**

Floors 1-4 hold on the code as written. A forged update is refused before any statement runs. Neither the
secret nor the bot token is returned by the API, logged on any path that ships, or printed by the CLI.
Finding F1 below is real but not reachable today; it is pinned as a strict `xfail` and does not block.

## 1. What an authenticated Telegram update can do (floor 1)

`POST /api/notifications/telegram/webhook` takes no user session. After the secret check it parses the body
and calls `telegram_service.handle_telegram_webhook`, which acts on one command only. `/start <code>` calls
`verify_link`, which looks up the single `telegram_links` row whose `link_token` equals the SHA-256 of the code
(SEC-014). It then sets that row's `chat_id`, `username` and `verified` and consumes the code. Every other text
gets a canned reply, and the reply is returned in the response body. No other table is read or written. No
other user's row can be named, because the only key is the digest of a 256-bit code that exists in plaintext
only in its owner's `POST /telegram/link` response.

So a forged update could pair an attacker's chat with an account only if the attacker also held that
account's pending code. Through the paired chat the attacker would then receive the account's notifications.
Before SEC-015 the code was the only lock. The header was compared with `!=` against `TELEGRAM_WEBHOOK_URL`,
a URL derivable from the public host, and `generate_telegram_link` even returns that URL's last segment to
every user as `bot_username`. An unset URL accepted every caller. The secret is now a second, independent
lock, and it holds before the handler runs. The pins check this with the real handler over MiniDB: a
forged `/start` that carries user B's *valid* code runs no statement and pairs nothing.

`verify_link` stays classified in `UNSCOPED_FUNCTION_ALLOWED` ("bot webhook: the link row is found by the
one-time token the user was issued"). That classification is unchanged and still true.

## 2. Secret handling (floor 2)

- **Comparison.** `hmac.compare_digest(received.encode(), expected.encode())`, once, and no `==`/`!=` on
  either value. Different lengths return early inside `compare_digest`, so the secret's length can leak. That
  is accepted: the length is not the secret, and Telegram allows 1-256 characters.
- **Fail closed.** If the secret is unset and `SINGLE_USER_MODE` is off, every call is rejected with the same
  403 body as a wrong secret. `SELF_HOSTED` multi-user is included. The "unset" branch is checked *before* the
  compare. Without that, `compare_digest(b"", b"")` would admit an empty header, and a mutant that does
  exactly this is caught. One warning per process, `telegram_webhook_secret_unset_rejecting_all`, carrying no
  value.
- **Never returned.** Outside `config.py`, `telegram_webhook_secret` is read only in `telegram_webhook` and
  `register_webhook`. `telegram_bot_token` is read only by the presence check in `generate_telegram_link`,
  `_telegram_configured`, `register_webhook` and `send_telegram_message` (a pinned static check). The 403
  body is a constant. The 200 body is the canned reply text.
- **`register_webhook`.** It posts `setWebhook {url, secret_token}` to `https://api.telegram.org/bot<token>/`.
  Its own log line is a valueless event. It does not catch httpx errors. The only caller, the CLI, catches
  `httpx.HTTPError` and prints the type name only, so a `ConnectError`/`ReadTimeout` whose text names the
  request URL never reaches the terminal. A `ValueError` (missing settings, or a non-JSON reply's
  `JSONDecodeError`) prints a message that holds no value. A Telegram rejection's `description` is never
  printed. All five outcomes are driven in a fresh process (so the CLI's own logging is the one in force):
  success, connect error, timeout, rejection, non-JSON. The bot token, its secret half and the webhook
  secret appear in none of them.
- **Existing send path.** `send_telegram_message` logs `exc_info=True` on failure. aiogram wraps aiohttp
  errors as `TelegramNetworkError(f"{type(e).__name__}: {e}") from e`. A refused connection names
  `host:port` only, and the traceback shows source lines, not locals. Pinned with a real aiogram session
  pointed at a closed local port. Only aiohttp errors whose text carries the URL (`InvalidURL`,
  `TooManyRedirects`) would embed the token. The first is pre-empted by aiogram's token validation; the
  second needs Telegram itself to redirect in a loop. Residual, not pinned.

### Finding F1 (not blocking): httpx logs the bot-token URL at INFO

httpx's own logger emits `HTTP Request: POST https://api.telegram.org/bot<token>/setWebhook "HTTP/1.1 200 OK"`
at INFO. I reproduced this with the app's `configure_logging("INFO")` and a mock transport. The comment
in `register_webhook` ("Never log the request") is therefore true of the app's code but not of the library.
The leak is **unreachable** today:

- the CLI calls `configure_logging("WARNING")` before dispatch, and in a fresh process `basicConfig` sets
  the root at WARNING;
- `register_webhook` has no other caller.

Both facts are pinned (`test_floor2_register_webhook_is_called_only_from_the_cli_at_warning`, plus the
subprocess CLI pins). The latent leak is a strict `xfail`
(`test_floor2_register_webhook_logs_no_bot_token_at_info`), checked to XPASS once the fix below is applied.

**Owed by `backend`:** in `app/core/logging.py:configure_logging`, cap `logging.getLogger("httpx")` and
`"httpcore"` at WARNING. That also covers any future httpx call whose URL carries a credential. Then remove the
marker.

## 3. Ruling: single-user mode with the secret unset accepts

**Acceptable; pinned as the ruled behaviour.** Reasons:

1. A single-user instance has one tenant. No update can reach another user's row, because there is none, so
   floor 1 cannot be engaged.
2. `check_single_user_mode` refuses to start unless the API is bound to loopback or the operator set
   `I_UNDERSTAND_NO_AUTH`. Anyone who can reach the webhook can already reach every other route as the
   default admin. The webhook secret would guard a side door in a house with no front door.
3. Even then, a forged update can pair a chat only with a valid pairing code. Pre-SEC-015 behaviour with no URL
   configured was the same.

Two pins keep the ruling honest. A **set** secret is still enforced in single-user mode (a mutant that lets
single-user bypass the compare is caught). The accept case has its own named test, so changing the ruling is
a deliberate edit. Recommended, not required: emit the same one-time warning in single-user mode, so an
operator who exposes the instance through a tunnel for Telegram sees it.

## 4. Pins added

`services/app/tests/safety/test_floor2_telegram_webhook_secret.py`, mapped in `FLOORS.md` (floor 2, "Telegram
webhook authenticity"): 24 tests plus 1 strict `xfail`.

- `compare_digest` used exactly once, with no `==`/`!=`/`in` on the header or secret and no
  `telegram_webhook_url` in the handler (static). A spy confirms the compare sees exactly the header and the
  secret.
- Nine forgeries (no header, empty, wrong, prefix, extended, upper-cased, the webhook URL, its last segment,
  the bot token) carry B's valid code. Each gets 403 of one shape, with no statement, no commit, no state
  change and no secret, token, code or digest in the log (real logging chain at DEBUG). The control: the
  correct secret pairs B only, leaves A's verified link alone, touches only `telegram_links`, and returns no
  secret. An unknown code mutates nothing.
- Unset secret, multi-user (cloud and self-hosted): four header shapes all 403 with no statement, one
  valueless warning. Single-user: unset accepts (ruling), set is enforced.
- Static read-site allowlist for the two settings. `register_webhook` is called or imported only from the
  CLI, and the CLI logs at WARNING.
- CLI in a fresh process across five outcomes: no token or secret printed, correct exit codes. The send path
  on a refused connection: no token in the log.

### Mutation check

19 mutations applied one at a time to a scratch copy of `services/app/` outside the worktree, each run against
the new file only (baseline 24 passed, 1 xfailed): **19/19 killed**. The mutations:

- `!=` instead of `compare_digest`;
- the URL as the secret (the old code);
- unset accepted in multi-user;
- unset falling through to the compare, so an empty header passes;
- single-user bypassing a set secret;
- a prefix compare;
- a case-insensitive compare;
- the warning logging the presented value;
- a warning on every call;
- a rejection logging the expected secret;
- the handler running before the check;
- the response echoing the secret;
- the CLI printing httpx's error text;
- the CLI at INFO;
- `register_webhook` logging the request URL;
- `register_webhook` printing Telegram's reply;
- `register_webhook` imported in `main.py`;
- the send path logging the token;
- the link endpoint returning the token as `bot_username`.

The first run left two survivors, both gaps in my pins, now closed. The unset-secret test's first call
carried no header, so a warning that logged the presented value logged `""`; the first call now carries a
value. The call-site guard ignored `from … import register_webhook`; it now counts imports.

## 5. Test runs and the environment

The shared venv now has **fastapi 0.143.2**, from `kit/retrofit`'s SEC-007 lift (`3fbebef`). This review
branch is based on `3f5e3ac`, which predates the lift and still expects `<0.137`. On this branch, 9
safety tests and 9 unit/contract tests fail, all route-enumeration guards (route sweep, anonymous caller,
consent gate, authn guard, onboarding and weak-spot contracts). That is the lazy-include breakage `FLOORS.md`
describes, and none of them involve Telegram. With the SEC-015 diff and these pins applied to a `kit/retrofit`
(`1d2a14a`) export in scratch, those 18 tests, the four route-guard files, `test_notifications.py`,
`test_telegram_register_webhook.py` and the new pins pass: 94 passed + 1 xfailed, and 46 passed + 13 skipped.
**The Orchestrator should land SEC-015 on top of SEC-007** (merge `kit/retrofit` into the task branch before
merging), not on `3f5e3ac`.

## 6. Residuals

1. **F1** (above): owed by `backend`, strict `xfail` until then.
2. **Bot username from the webhook URL.** `generate_telegram_link` returns `TELEGRAM_WEBHOOK_URL.split("/")[-1]`
   as `bot_username`, so the deep link is `t.me/webhook?start=…`. That is a functional bug, not a floor issue,
   now that the URL is not a secret. Recommended for `backend`: a `TELEGRAM_BOT_USERNAME` setting or `getMe`.
3. **Secret strength is not validated.** Any non-empty value is accepted at startup. Telegram itself rejects
   values outside 1-256 `[A-Za-z0-9_-]` at `setWebhook`, and the CLI then exits 1. Recommended: a config
   validator requiring at least 32 characters of that alphabet.
4. **Operations.** A multi-user deploy without `TELEGRAM_WEBHOOK_SECRET` rejects every update, so Telegram
   pairing stops by design until the operator sets the secret and runs `python -m app.cli
   register-telegram-webhook`. Rotating the secret is the same two steps, and updates in between are refused
   (Telegram retries).
5. **Pairing codes still never expire** (R-048, open).

## 7. Follow-up review: `backend` `b69f8a5` (red), `8285ca4` (fix)

### Verdict: **APPROVE**

Reviewed on `kit/retrofit` (`548aef5`) with both commits cherry-picked. Floors 1, 3 and 4 are untouched; floor 2
improves. One new non-blocking finding (F2), pinned as a strict `xfail`.

### What changed

- **F1 fixed.** `configure_logging` caps `httpx`, `httpcore`, `googleapiclient` and `stripe` at `WARNING`
  whatever the root level. The strict `xfail` on `test_floor2_register_webhook_logs_no_bot_token_at_info` is
  gone and the test passes for the right reason: on a scratch copy with the `httpx`/`httpcore` cap removed it
  fails on `assert value not in text` for the bot token, not on the setup line.
- **Residual 2 fixed.** `TELEGRAM_BOT_USERNAME` builds the deep link. Unset, the endpoint returns 400 before a
  link token is issued, and the response never carries the bot token. Not a floor issue.
- **Residual 3 fixed.** `TELEGRAM_WEBHOOK_SECRET` must be 32-256 characters of `[A-Za-z0-9_-]`; unset is
  still allowed and fails closed. The validator's message names the rule, never the value.
- **`hide_input_in_errors: True` on the whole `Settings` model.** Endorsed. Without it a pydantic
  `ValidationError` prints `input_value=<the raw value>` for any field, and a startup crash goes to the
  container log. That covers every `SecretStr` setting and also plain-`str` settings that carry credentials
  (`DATABASE_URL`, `REDIS_URL`). Two limits: it governs `str()`/`repr()` only (`exc.errors()` still carries
  `input`, and nothing in `app/` calls it on a settings error), and a validator that interpolates the value
  into its own message bypasses it (`_validate_registration_mode` does, harmlessly, since the value is not a
  secret). A future validator on a secret must not do that. The new pins cover the validator path for the
  webhook secret.

### Other libraries checked

Grepped each library's own log calls and probed the ones the app imports, with the root logger at `DEBUG`:

| Library | At `INFO` | At `DEBUG` | Action |
|---|---|---|---|
| `aiogram` | Dispatcher/event lines only (bot id, the token's public half); the app uses `Bot` for sending only | same | none |
| `aiohttp` (client) | nothing | nothing | none |
| `authlib` (client) | nothing; requests go through `httpx`, capped | server-grant lines only, unused | none |
| `google-auth` | nothing | `request_log` prints raw headers (`Authorization: Bearer …`), but the `google` base logger is set to `propagate=False` unless configured, so nothing reaches the root handler | none; do **not** configure the `google` logger below `WARNING` |
| `requests_oauthlib` (Calendar `Flow.fetch_token`) | nothing | the token request body (client secret, auth code) and `Obtained token …` (the user's refresh token) | **F2** |
| `botocore` / `boto3` | nothing | `Sending http request` with signed headers; probe showed `X-Amz-Security-Token` and the access key id in the log | **F2** |
| `urllib3` (`requests`: Web Push, Google token refresh) | nothing | request line with path; a Web Push endpoint path is a bearer capability | **F2** |
| `openai`, `anthropic` | `Retrying request to <path>` only | request options (no auth header), response headers | none; pinned below |

### Finding F2 (not blocking): credential-bearing loggers are uncapped at `DEBUG`

At the default `LOG_LEVEL=INFO` nothing leaks. `LOG_LEVEL` is a documented operator knob, though, and at `DEBUG`
the three libraries above write a user's Google refresh token, the Google client secret, STS session tokens and
Web Push capability paths to the log. F1 was capped "whatever the root level", and these should be treated the
same way. **Owed by `backend`:** add `requests_oauthlib`, `oauthlib`, `botocore`, `boto3` and `urllib3` to
`_URL_LOGGING_LIBRARIES`. Verified on a scratch copy: with those five capped, the probe prints none of the
session token, the access key id or the push path, and the strict `xfail` fails as it should, so the marker
comes off with the fix.

### Pins added: `tests/safety/test_floor2_library_log_levels.py`

- The four capped libraries stay at `WARNING` or above after `configure_logging("DEBUG")`, starting from
  `NOTSET`, so a pass is `configure_logging`'s doing.
- F2 as a strict `xfail`.
- A per-user key handed to the OpenAI and Anthropic adapters never reaches the log at `DEBUG`, on a 200 or a
  401. Each test also asserts that the key reached the transport, so it cannot pass vacuously.
- No `Settings` `ValidationError` echoes the value of any `SecretStr` field (14 today, discovered from the
  model, with a guard against an empty list), and a malformed `TELEGRAM_WEBHOOK_SECRET` read from the
  environment is not echoed either.

Mutation check on a scratch copy, new file only (baseline 24 passed, 1 xfailed). Cap removed: 2 red. Plus
`hide_input_in_errors` removed: 15 red. Key logged in each adapter: 4 red. F2 set capped: the `xfail` fails.
The first settings run passed with `hide_input_in_errors` removed. The cause was that pydantic elides the
middle of a long `input_value`, so a 38-character probe never appeared whole. The probe is now 8
characters, and a comment says why. `backend`'s own `test_telegram_settings.py` does not have this problem,
because it also asserts that `input_value` is absent.

### Residuals from this round

1. **F2**: owed by `backend`, strict `xfail` until then.
2. **Deploy: the secret minimum is stricter than before.** The new validator refuses a secret shorter than 32
   characters, so the app **will not start**. That is loud, and it fails closed, but a deployment whose
   current secret is shorter goes down on deploy. The Orchestrator should confirm the production secret's
   length (the user's secret store, not the server's `.env`) before this ships. `token_urlsafe(32)`, the
   documented generator, gives 43 characters.
3. **Docs drift (not a floor issue).** `.env.example`, `docs/deployment.md` § Telegram webhook secret and the
   `config.py` comment still say "1-256 chars". `TELEGRAM_BOT_USERNAME` is not in `.env.example` or the
   deployment guide, so telegram linking returns 400 until an operator finds it. Owners: `backend`
   (`config.py`), `devops`/docs.

### Test run

`cd services/app && .venv/bin/python -m pytest tests/safety -q --cov=tests/safety --cov-fail-under=95` gave
`805 passed, 1 skipped, 1 xfailed`, total coverage 97.79%. The `xfail` is F2. `backend`'s
`test_logging.py`, `test_telegram_settings.py` and `test_notifications.py`: 31 passed.
