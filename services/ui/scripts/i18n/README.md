# i18n tooling

Three scripts, in the order you use them. They exist because translating this
UI by hand means visiting 124 files, and because "we translated everything" is
a claim that decays the week after it is made.

| Script | What it does |
|---|---|
| `scan.mjs` | Finds user-visible strings **not** wrapped in `t()`. Walks the TypeScript AST — JSX text nodes, prose-carrying attributes, `toast()` messages — so multi-line prose is caught the same as a one-liner. Run with no arguments for a per-file count. |
| `transform.mjs` | Wraps what `scan.mjs` finds, and gives each owning component `const { t } = useTranslation()`. Every edit is a precise AST span replacement. Pass file paths to limit it, `--dry` to count without writing. |
| `fragments.mjs` | Lists sentences split across expressions — `{t('Week')} {week}`. These render correctly in English and badly in a language that orders words differently, so they need converting to one interpolated key: `t('Week {{week}}', { week })`. |

`dynamic-keys.mjs` regenerates `dynamic-keys.json`: the keys that reach `t()`
through a variable (`t(label)`, `t(EVENT_LABELS[e])`). They are derived from the
tables they live in, never hand-listed — a hand-written list is what let the
theme labels, the tour copy and the notification event names sit untranslated
behind a green guard. `keys.mjs` prints every key in use.

## The guard

`src/i18n/coverage.test.ts` runs `scan.mjs` on every test run and fails if
anything is left untranslated, if a key has no Russian entry, or if the Russian
bundle carries an entry nobody uses. That is what keeps coverage full: a new
untranslated string fails in the author's own test run, when it costs one line
to fix, rather than surfacing months later as a Russian user meeting an English
screen.

## The static guard is necessary, not sufficient

Run the app and look at it. A static scan cannot see:

- **a table rendered without `t()`** — the keys are declared and translated, and
  the component still prints English (`tabLabels[tab]`, `f.label`);
- **dates** — `toLocaleDateString(undefined, …)` follows the browser, not the
  app's language;
- **third-party defaults** — Sonner labelled its live region "Notifications" in
  English whatever the app was set to.

All three shipped green and were caught by loading the app in Russian and
walking the routes. The sweep that found them: set the language, visit each
route, and collect any text node or `aria-label`/`title`/`placeholder` still
matching `[A-Za-z]{4,}`. Do the same pass in English afterwards, looking for
raw `{{placeholders}}` and stray `${…}` — that is what catches a key that was
wrapped wrongly.

## Conventions

- **English is the key set.** `t('Save changes')`, not `t('settings.save')`, so
  a missing Russian entry renders as correct English rather than a raw key.
- **Toasts use `i18n.t()`, not the hook.** They fire imperatively and never
  re-render, and keeping `t` out of effect and `useCallback` dependency arrays
  avoids breaking the memoization those call sites were written for.
- **Class components and plain helper functions use `i18n.t()`** — no hooks
  available.
- **Counts are interpolated**, never concatenated: `t('{{count}} day')` with
  `_one`/`_other` in English and `_one`/`_few`/`_many`/`_other` in Russian.
  English needs its own entries here, or the key renders as written: "5 day".

## Adding a language

1. Add the tag to `SUPPORTED_LANGUAGES` in `src/i18n/index.ts` and to
   `settings_service.SUPPORTED_LANGUAGES` — the API rejects anything else, so a
   tag added on one side only is a save that silently fails.
2. Add `src/locales/<tag>/common.json`, and register it in `resources`.
3. `node scripts/i18n/keys.mjs` lists every key that needs an entry.
