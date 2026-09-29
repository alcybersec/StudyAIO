/**
 * Regenerate `dynamic-keys.json`.
 *
 * Some keys reach `t()` through a variable — `t(label)`, `t(w.label)`,
 * `t(EVENT_LABELS[event])` — and no scanner can follow that. The strings live
 * in module-level tables instead, so this collects them: for any file that
 * calls `t()` with something other than a literal, every prose string in its
 * top-level `const` tables becomes a declared key.
 *
 * Hand-maintaining this list is what let the theme labels, the tour copy and
 * the notification event names sit untranslated behind a green guard. The list
 * is derived now, and the guard compares the checked-in file against a fresh
 * run so it cannot drift again.
 */
import ts from 'typescript'
import fs from 'node:fs'
import { sourceFiles } from './scan.mjs'
import { tsFiles } from './scan-ts.mjs'

//: Variant tables hold Tailwind class lists under exactly the property names
//: prose uses (`label`, `text`), so they have to be told apart by shape.
//: A Tailwind token always carries a `-`, a `:` or a `/` — "here." and "was"
//: must not look like one, which a bare `w|h` prefix made them do.
const CSS_TOKEN = /^(?:(?:bg|text|border|p[xytblr]?|m[xytblr]?|w|h|gap|rounded|ring|flex|grid|font|shadow|opacity|inset|top|left|right|bottom|space|size|leading|tracking|truncate|overflow|cursor|transition|animate|z|col|row|min|max|hover|focus|focus-visible|disabled|sm|md|lg|xl|dark|group|peer|absolute|relative|fixed|sticky|block|inline|hidden|items|justify|self|order|object|origin|scale|rotate|translate|whitespace|break|select|pointer|outline|underline|decoration|backdrop|aspect|basis|shrink|grow|first|last|odd|even)(?:[-:/][-\w[\]/.%:()]*)?)$/
const CSS_LIKE = (v) => {
  const tokens = v.trim().split(/\s+/)
  return tokens.length > 0 && tokens.every((t) => CSS_TOKEN.test(t))
}
const prose = (v) =>
  /[A-Za-z]{2,}/.test(v) &&
  !/^(?:https?:|\/|#|[a-z]+(?:[-_][a-z]+)+$)/.test(v) &&
  !CSS_LIKE(v)

export function generate() {
  const keys = new Set()

  for (const file of [...sourceFiles('src'), ...tsFiles('src')]) {
    const src = fs.readFileSync(file, 'utf8')
    const sf = ts.createSourceFile(file, src, ts.ScriptTarget.Latest, true,
      file.endsWith('.tsx') ? ts.ScriptKind.TSX : ts.ScriptKind.TS)

    // Deliberately not filtered to files that call t() dynamically: a table and
    // the component that indexes into it usually live in different files —
    // WidgetRegistry.ts holds the labels, DashboardCustomizer renders them.
    // Filtering on the call site dropped 32 real keys and is why the first
    // version of this list was wrong.

    // Top-level `const` tables only: those are the lookup tables a component
    // indexes into, as opposed to strings built inside a function.
    for (const stmt of sf.statements) {
      if (!ts.isVariableStatement(stmt)) continue
      const collect = (n) => {
        if (ts.isPropertyAssignment(n) && ts.isStringLiteral(n.initializer)) {
          const name = n.name.getText(sf).replace(/['"]/g, '')
          if (['label', 'title', 'description', 'desc', 'hint', 'text', 'name'].includes(name) &&
              prose(n.initializer.text)) {
            keys.add(n.initializer.text)
          }
        } else if (ts.isStringLiteral(n) && ts.isPropertyAssignment(n.parent) === false &&
                   n.parent && ts.isObjectLiteralExpression(n.parent) === false) {
          // values of a Record<string, string> written as `key: 'Value'` are
          // covered above; nothing else in a table is user-facing by default
        }
        ts.forEachChild(n, collect)
      }
      collect(stmt)
      // A bare `const MESSAGE = '…'` passed to t() by name, e.g.
      // SECOND_FACTOR_REJECTED on the login page.
      for (const decl of stmt.declarationList.declarations) {
        if (decl.initializer && ts.isStringLiteral(decl.initializer) &&
            /\s/.test(decl.initializer.text) && prose(decl.initializer.text)) {
          keys.add(decl.initializer.text)
        }
      }
      // Record<K, string> tables: every string value, keyed by anything.
      const recordValues = (n) => {
        if (ts.isPropertyAssignment(n) && ts.isStringLiteral(n.initializer) &&
            ts.isObjectLiteralExpression(n.parent)) {
          const decl = stmt.declarationList.declarations[0]
          const typeText = decl?.type ? decl.type.getText(sf) : ''
          if (/Record<[^,]+,\s*string\s*>/.test(typeText) && prose(n.initializer.text)) {
            keys.add(n.initializer.text)
          }
        }
        ts.forEachChild(n, recordValues)
      }
      recordValues(stmt)
    }
  }
  return [...keys].sort()
}

if (process.argv[1]?.endsWith('dynamic-keys.mjs')) {
  const keys = generate()
  fs.writeFileSync('scripts/i18n/dynamic-keys.json', JSON.stringify(keys, null, 2) + '\n')
  console.log(`${keys.length} dynamic keys`)
}
