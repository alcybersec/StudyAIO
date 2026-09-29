/**
 * Structural guard: the UI stays fully translated.
 *
 * "Full coverage" is a claim that decays the moment someone adds a screen, so
 * it is checked rather than asserted in a changelog. Two rules:
 *
 *   1. No user-visible string is left outside `t()`. The scanner walks the
 *      TypeScript AST — JSX text nodes, prose-carrying attributes, toast
 *      messages — so multi-line prose is caught the same as a one-liner.
 *   2. Every key in use has a Russian entry, or plural forms for one.
 *
 * A new untranslated string fails rule 1 in the author's own test run, when it
 * costs one line to fix. Without this, the failure surfaces as a Russian user
 * meeting an English screen months later, which nobody reports as a bug.
 */
/// <reference types="node" />
import { describe, expect, it } from 'vitest'
import { readFileSync } from 'node:fs'
import { collect, sourceFiles } from '../../scripts/i18n/scan.mjs'
import { collectTs, tsFiles } from '../../scripts/i18n/scan-ts.mjs'
import { generate as generateDynamicKeys } from '../../scripts/i18n/dynamic-keys.mjs'
import ru from '../locales/ru/common.json'

const PLURAL_SUFFIXES = ['_one', '_few', '_many', '_other']

function keysInUse(): string[] {
  const KEY = /\b(?:i18n\.)?t\(\s*(?:'((?:[^'\\]|\\.)*)'|"((?:[^"\\]|\\.)*)")/g
  const keys = new Set<string>()
  // i18n/index.ts documents the convention with example t() calls; they are
  // prose about the key set, not members of it.
  const files = [...sourceFiles('src'), ...tsFiles('src')].filter(
    (f) => !f.endsWith('src/i18n/index.ts'),
  )
  for (const file of files) {
    const src = readFileSync(file, 'utf8')
    for (const m of src.matchAll(KEY)) {
      keys.add((m[1] ?? m[2]).replace(/\\'/g, "'").replace(/\\"/g, '"'))
    }
  }
  // Keys reaching t() through a variable live in tables the scanner cannot
  // follow; they are listed so they are still checked for a translation.
  const dynamic: string[] = JSON.parse(readFileSync('scripts/i18n/dynamic-keys.json', 'utf8'))
  for (const k of dynamic) keys.add(k)
  return [...keys]
}

describe('i18n coverage', () => {
  it('leaves no user-visible string outside t()', () => {
    const offenders: string[] = []
    for (const file of sourceFiles('src')) {
      for (const hit of collect(file).hits) {
        offenders.push(`${file}: [${hit.kind}] ${hit.text.slice(0, 70)}`)
      }
    }

    expect(offenders).toEqual([])
  })

  it('leaves no user-visible string in a plain .ts module either', () => {
    // The JSX scanner walks .tsx only, which once exempted every zod
    // validation message — the error under each form field — plus the shared
    // toast helpers. A string does not stop being user-visible for living in
    // a module with no JSX in it.
    const dynamic: string[] = JSON.parse(readFileSync('scripts/i18n/dynamic-keys.json', 'utf8'))
    const offenders: string[] = []
    for (const file of tsFiles('src')) {
      for (const hit of collectTs(file).hits) {
        // Copy that reaches t() through a variable is translated at the render
        // site, so it is declared rather than wrapped where it is defined.
        if (dynamic.includes(hit.text)) continue
        offenders.push(`${file}: [${hit.kind}] ${hit.text.slice(0, 70)}`)
      }
    }

    expect(offenders).toEqual([])
  })

  it('keeps the generated dynamic-key list current', () => {
    // Keys that reach t() through a variable are derived from the tables they
    // live in, not listed by hand. Hand-listing is what let the theme labels,
    // the tour copy and the notification event names sit untranslated behind
    // a green guard: the list was the thing that was incomplete.
    const onDisk: string[] = JSON.parse(readFileSync('scripts/i18n/dynamic-keys.json', 'utf8'))

    expect(generateDynamicKeys()).toEqual(onDisk)
  })

  it('has a Russian entry for every key in use', () => {
    const untranslated = keysInUse().filter(
      (k) =>
        !(k in ru) && !PLURAL_SUFFIXES.some((s) => `${k}${s}` in (ru as Record<string, string>)),
    )

    expect(untranslated).toEqual([])
  })

  it('carries no Russian entry for a key nobody uses', () => {
    // A stale entry is not a bug a user sees, but it is a translation someone
    // paid attention to that no longer means anything — and it hides the real
    // count of what is covered.
    const inUse = new Set(keysInUse())
    const stale = Object.keys(ru).filter((k) => {
      const base = PLURAL_SUFFIXES.reduce((acc, s) => (acc.endsWith(s) ? acc.slice(0, -s.length) : acc), k)
      return !inUse.has(base)
    })

    expect(stale).toEqual([])
  })
})
