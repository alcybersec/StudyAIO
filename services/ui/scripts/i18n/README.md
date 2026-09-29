# i18n tooling

Three scripts, in the order you use them. They exist because translating this
UI by hand means visiting 124 files, and because "we translated everything" is
a claim that decays the week after it is made.

| Script | What it does |
|---|---|
| `scan.mjs` | Finds user-visible strings **not** wrapped in `t()`. Walks the TypeScript AST — JSX text nodes, prose-carrying attributes, `toast()` messages — so multi-line prose is caught the same as a one-liner. Run with no arguments for a per-file count. |
| `transform.mjs` | Wraps what `scan.mjs` finds, and gives each owning component `const { t } = useTranslation()`. Every edit is a precise AST span replacement. Pass file paths to limit it, `--dry` to count without writing. |
| `fragments.mjs` | Lists sentences split across expressions — `{t('Week')} {week}`. These render correctly in English and badly in a language that orders words differently, so they need converting to one interpolated key: `t('Week {{week}}', { week })`. |

`keys.mjs` prints every key in use, including the ones reaching `t()` through a
variable (listed in `dynamic-keys.json`, since no scanner can follow those).

## The guard

`src/i18n/coverage.test.ts` runs `scan.mjs` on every test run and fails if
anything is left untranslated, if a key has no Russian entry, or if the Russian
bundle carries an entry nobody uses. That is what keeps coverage full: a new
untranslated string fails in the author's own test run, when it costs one line
to fix, rather than surfacing months later as a Russian user meeting an English
screen.

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
