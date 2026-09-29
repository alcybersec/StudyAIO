/**
 * The .ts half of the sweep.
 *
 * The JSX scanner walks .tsx only, which silently exempted every string that
 * lives in a plain module: zod validation messages (the errors under every
 * form field), the shared toast helpers, and the constant tables that feed
 * labels into components through a variable.
 */
import ts from 'typescript'
import fs from 'node:fs'
import path from 'node:path'

// Object properties whose value a person reads.
const PROSE_PROPS = new Set([
  'message', 'label', 'title', 'description', 'desc', 'hint', 'text', 'placeholder',
  'emptyTitle', 'emptyHint', 'emptyActionLabel', 'actionLabel', 'subtitle', 'name',
])
const SKIP = /^(?:https?:|\/|#|[\w.+-]+@|[a-z]+(?:-[a-z]+)+$)/

export function tsFiles(root = 'src') {
  const out = []
  const walk = (d) => {
    for (const e of fs.readdirSync(d, { withFileTypes: true })) {
      const p = path.join(d, e.name)
      if (e.isDirectory()) { if (e.name !== 'locales') walk(p) }
      else if (/\.ts$/.test(e.name) && !e.name.includes('.test.') && !e.name.endsWith('.d.ts')) out.push(p)
    }
  }
  walk(root)
  return out.sort()
}

const isTranslationCall = (n) =>
  ts.isCallExpression(n) &&
  ((ts.isIdentifier(n.expression) && n.expression.text === 't') ||
    (ts.isPropertyAccessExpression(n.expression) && n.expression.name.text === 't'))

export function collectTs(file) {
  const src = fs.readFileSync(file, 'utf8')
  const sf = ts.createSourceFile(file, src, ts.ScriptTarget.Latest, true, ts.ScriptKind.TS)
  const hits = []
  const prose = (v) => /[A-Za-z]{2,}/.test(v) && /\s/.test(v) && !SKIP.test(v)

  const visit = (n) => {
    if (isTranslationCall(n)) return
    if (ts.isPropertyAssignment(n) && ts.isStringLiteral(n.initializer)) {
      const key = n.name.getText(sf).replace(/['"]/g, '')
      if (PROSE_PROPS.has(key) && prose(n.initializer.text)) {
        hits.push({ kind: `prop:${key}`, node: n.initializer, text: n.initializer.text })
      }
    }
    if (ts.isCallExpression(n) && ts.isPropertyAccessExpression(n.expression) &&
        ts.isIdentifier(n.expression.expression) && n.expression.expression.text === 'toast') {
      const dig = (x) => {
        if (isTranslationCall(x)) return
        if (ts.isStringLiteral(x) && prose(x.text)) hits.push({ kind: 'toast', node: x, text: x.text })
        else ts.forEachChild(x, dig)
      }
      for (const a of n.arguments) dig(a)
    }
    ts.forEachChild(n, visit)
  }
  visit(sf)
  return { sf, src, hits }
}

if (process.argv[1]?.endsWith('scan-ts.mjs')) {
  let total = 0
  for (const f of tsFiles()) {
    const { sf, hits } = collectTs(f)
    for (const h of hits) {
      const line = sf.getLineAndCharacterOfPosition(h.node.getStart(sf)).line + 1
      console.log(`${f}:${line} [${h.kind}] ${h.text}`)
      total++
    }
  }
  console.log(`\nTOTAL=${total}`)
}
