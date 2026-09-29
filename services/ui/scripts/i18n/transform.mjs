/**
 * Wrap user-visible strings in t(), and give each owning component the hook.
 *
 * AST-driven: every edit is a precise span replacement, so multi-line JSX text
 * and attribute literals are handled the same way. `tsc` is the safety net —
 * a component left without `t` in scope fails to compile rather than shipping.
 */
import ts from 'typescript'
import fs from 'node:fs'
import path from 'node:path'
import { collect, sourceFiles } from './scan.mjs'

const only = process.argv.slice(2).filter((a) => !a.startsWith('--'))
const DRY = process.argv.includes('--dry')

function jsString(s) {
  if (!s.includes("'")) return `'${s}'`
  if (!s.includes('"')) return `"${s}"`
  return `'${s.replace(/'/g, "\\'")}'`
}

/** Where the hook goes, and how, for one owning function. */
function hookPlan(owner, sf) {
  if (!owner || owner.isClass || !owner.isComponent) return null
  const fn = owner.node
  const body = fn.body
  if (!body) return null
  if (ts.isBlock(body)) {
    const alreadyHas = body.statements.some((s) => /useTranslation\(\)/.test(s.getText(sf)))
    if (alreadyHas) return null
    return { kind: 'block', pos: body.getStart(sf) + 1 }
  }
  // Concise arrow body: give it a block so the hook has somewhere to live.
  return { kind: 'concise', start: body.getStart(sf), end: body.getEnd() }
}

let changedFiles = 0
let changedStrings = 0
const fragmented = []
const needsInterpolation = []

for (const file of (only.length ? only : sourceFiles())) {
  const { sf, src, hits } = collect(file)
  if (!hits.length) continue

  const edits = []
  const owners = new Map()

  for (const h of hits) {
    // A template *expression* cannot be auto-wrapped: its key would contain a
    // literal `${…}`, which renders as that text. Wrapping one produced ~30
    // visible regressions before this guard existed. Report and leave it.
    if (/\$\{/.test(h.text)) {
      needsInterpolation.push(`${file}: ${h.text.slice(0, 80)}`)
      continue
    }
    const key = jsString(h.text)
    // A toast is fired imperatively, at a moment, and never re-renders — so it
    // reads the language directly rather than through the hook. That also keeps
    // `t` out of effect and useCallback dependency arrays, where adding it
    // breaks the memoization those call sites were written for.
    const useHook = h.kind !== 'toast' && h.owner && h.owner.isComponent && !h.owner.isClass
    const ownerIsComponent = useHook
    const call = useHook ? `t(${key})` : `i18n.t(${key})`

    if (h.kind === 'text') {
      const raw = h.node.getFullText(sf)
      const start = h.node.getFullStart()
      const lead = raw.match(/^\s*/)[0]
      const trail = raw.match(/\s*$/)[0]
      edits.push({ start: start + lead.length, end: start + raw.length - trail.length, text: `{${call}}` })
      // Text split across sibling expressions makes a poor translation unit.
      const siblings = (h.node.parent.children ?? []).filter(
        (c) => ts.isJsxText(c) && /[A-Za-z]{2,}/.test(c.text),
      )
      if (siblings.length > 1) fragmented.push(`${file}: ${h.text}`)
    } else if (h.kind === 'toast' || h.kind === 'child') {
      // Already inside an expression — the literal is replaced in place, with
      // no braces of its own.
      edits.push({ start: h.node.getStart(sf), end: h.node.getEnd(), text: call })
    } else {
      // attribute string literal -> {t('...')}, replacing the whole initializer
      const attr = h.node.parent
      const init = ts.isJsxAttribute(attr) ? attr.initializer : h.node
      edits.push({ start: init.getStart(sf), end: init.getEnd(), text: `{${call}}` })
    }
    changedStrings++

    if (ownerIsComponent) {
      const plan = hookPlan(h.owner, sf)
      if (plan) owners.set(h.owner.node, plan)
    }
  }

  for (const plan of owners.values()) {
    if (plan.kind === 'block') {
      edits.push({ start: plan.pos, end: plan.pos, text: `\n  const { t } = useTranslation()\n` })
    } else {
      const body = src.slice(plan.start, plan.end)
      edits.push({
        start: plan.start,
        end: plan.end,
        text: `{\n  const { t } = useTranslation()\n\n  return ${body}\n}`,
      })
    }
  }

  const needsHookImport = [...owners.keys()].length > 0
  const needsI18nImport = hits.some((h) => !(h.owner && h.owner.isComponent && !h.owner.isClass))

  let out = src
  for (const e of edits.sort((a, b) => b.start - a.start || b.end - a.end)) {
    out = out.slice(0, e.start) + e.text + out.slice(e.end)
  }

  const imports = []
  if (needsHookImport && !/from 'react-i18next'/.test(out)) {
    imports.push(`import { useTranslation } from 'react-i18next'`)
  }
  if (needsI18nImport && !/^import i18n from /m.test(out)) {
    const rel = path.relative(path.dirname(file), 'src/i18n').split(path.sep).join('/')
    imports.push(`import i18n from '${rel.startsWith('.') ? rel : './' + rel}'`)
  }
  if (imports.length) {
    const firstImport = out.indexOf('import ')
    const insertAt = firstImport === -1 ? 0 : out.indexOf('\n', firstImport) + 1
    out = out.slice(0, insertAt) + imports.join('\n') + '\n' + out.slice(insertAt)
  }

  if (out !== src) {
    changedFiles++
    if (!DRY) fs.writeFileSync(file, out)
  }
}

console.log(`files=${changedFiles} strings=${changedStrings}`)
if (needsInterpolation.length) {
  console.log(`\nNEEDS INTERPOLATION BY HAND (${needsInterpolation.length}) — a template`)
  console.log(`expression must become one key with {{placeholders}}:`)
  for (const n of needsInterpolation) console.log('  ' + n)
}
if (fragmented.length) {
  console.log(`\nFRAGMENTED (${fragmented.length}) — sentences split across expressions:`)
  for (const f of fragmented.slice(0, 40)) console.log('  ' + f)
}
