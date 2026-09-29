import ts from 'typescript'
import fs from 'node:fs'
import path from 'node:path'

const VISIBLE_ATTRS = new Set([
  'label','title','placeholder','aria-label','subtitle','description','actionLabel',
  'alt','content','heading','emptyMessage','confirmLabel','cancelLabel','detail',
  'tooltip','caption','hint','summaryText','buttonLabel','emptyText','ariaLabel',
  // Prose-carrying props this codebase defines itself, found by scanning every
  // JSX attribute whose literal value reads like a sentence (scripts/i18n/attrs.mjs)
  // rather than by guessing which names matter.
  'emptyTitle','emptyHint','emptyActionLabel','message',
])
// Values that are examples/formats, not prose to translate.
const SKIP_VALUE = /^(?:[\w.+-]+@[\w.-]+|https?:\/\/|\/|#|[A-Z]+-X+$)/
const ENTITIES = {
  '&amp;': '&', '&apos;': "'", '&rsquo;': '’', '&lsquo;': '‘',
  '&ldquo;': '“', '&rdquo;': '”', '&mdash;': '—', '&ndash;': '–',
  '&hellip;': '…', '&times;': '×', '&middot;': '·', '&nbsp;': ' ',
  '&lt;': '<', '&gt;': '>', '&quot;': '"',
}

export function decode(s) {
  return s.replace(/&[a-z]+;/g, (m) => ENTITIES[m] ?? m)
}
export function normalize(s) {
  return decode(s).replace(/\s+/g, ' ').trim()
}
function hasLetters(s) {
  // Letters inside `${…}` are an expression, not prose to translate.
  return /[A-Za-z]{2,}/.test(s.replace(/\$\{[^}]*\}/g, ' '))
}

const isTranslationCall = (n) =>
  ts.isCallExpression(n) &&
  ((ts.isIdentifier(n.expression) && n.expression.text === 't') ||
    (ts.isPropertyAccessExpression(n.expression) && n.expression.name.text === 't'))

export function collect(file) {
  const src = fs.readFileSync(file, 'utf8')
  const sf = ts.createSourceFile(file, src, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX)
  const hits = []

  const enclosingComponent = (node) => {
    let n = node.parent
    let nearestFn = null
    while (n) {
      if (ts.isFunctionDeclaration(n) || ts.isFunctionExpression(n) || ts.isArrowFunction(n)) {
        let name = null
        if (ts.isFunctionDeclaration(n) && n.name) name = n.name.text
        else if (ts.isFunctionExpression(n) && n.name) name = n.name.text
        else if (n.parent && ts.isVariableDeclaration(n.parent) && ts.isIdentifier(n.parent.name)) {
          name = n.parent.name.text
        }
        if (!nearestFn) nearestFn = { node: n, name }
        if (name && (/^[A-Z]/.test(name) || /^use[A-Z]/.test(name))) return { node: n, name, isComponent: true }
      }
      if (ts.isClassDeclaration(n)) return { node: n, name: n.name?.text ?? null, isClass: true }
      n = n.parent
    }
    return nearestFn ? { ...nearestFn, isComponent: false } : null
  }

  const visit = (node) => {
    if (ts.isJsxText(node)) {
      const text = normalize(node.text)
      if (text && hasLetters(text)) {
        hits.push({ kind: 'text', node, text, owner: enclosingComponent(node) })
      }
    } else if (ts.isJsxAttribute(node) && node.initializer) {
      const attr = node.name.getText(sf)
      let lit = null
      const inner =
        ts.isJsxExpression(node.initializer) ? node.initializer.expression : node.initializer
      if (ts.isStringLiteral(node.initializer)) lit = node.initializer
      else if (inner && ts.isStringLiteral(inner)) lit = inner
      // A template literal is prose too. `title={`Theme: ${label}`}` reads to a
      // user exactly like a quoted string, and nine of them sat untranslated
      // behind a scanner that only knew about StringLiteral.
      else if (inner && (ts.isTemplateExpression(inner) || ts.isNoSubstitutionTemplateLiteral(inner))) {
        const raw = inner.getText(sf)
        const prose = raw.replace(/\$\{[^}]*\}/g, ' ')
        if (/[A-Za-z]{2,}/.test(prose) && VISIBLE_ATTRS.has(attr)) {
          hits.push({
            kind: `attr:${attr}`,
            node: inner,
            text: normalize(raw.slice(1, -1)),
            owner: enclosingComponent(node),
          })
        }
      }
      if (lit && VISIBLE_ATTRS.has(attr)) {
        const text = normalize(lit.text)
        if (text && hasLetters(text) && !SKIP_VALUE.test(text)) {
          hits.push({ kind: `attr:${attr}`, node: lit, text, owner: enclosingComponent(node) })
        }
      }
    } else if (ts.isJsxExpression(node) && node.expression &&
               node.parent && (ts.isJsxElement(node.parent) || ts.isJsxFragment(node.parent))) {
      // A JSX *child* expression: `{cond ? 'Save' : 'Saving…'}` and
      // `{`${n} left`}` read exactly like text, and the live sweep found a
      // dozen of them behind a scanner that only looked at JsxText.
      //
      // Only this expression's own top-level branches are examined. Descending
      // further would sweep in className strings and every literal inside a
      // nested map callback — the first attempt reported 1553 "findings".
      const branches = []
      const consider = (n) => {
        if (!n || isTranslationCall(n)) return
        if (ts.isStringLiteral(n) || ts.isNoSubstitutionTemplateLiteral(n) || ts.isTemplateExpression(n)) {
          branches.push(n)
        } else if (ts.isConditionalExpression(n)) {
          consider(n.whenTrue)
          consider(n.whenFalse)
        } else if (ts.isBinaryExpression(n) &&
                   (n.operatorToken.kind === ts.SyntaxKind.AmpersandAmpersandToken ||
                    n.operatorToken.kind === ts.SyntaxKind.BarBarToken ||
                    n.operatorToken.kind === ts.SyntaxKind.QuestionQuestionToken)) {
          consider(n.right)
        } else if (ts.isParenthesizedExpression(n)) {
          consider(n.expression)
        }
      }
      consider(node.expression)
      for (const lit of branches) {
        const raw = ts.isStringLiteral(lit) ? lit.text : lit.getText(sf).slice(1, -1)
        const text = normalize(raw)
        if (text && hasLetters(text) && !SKIP_VALUE.test(text)) {
          hits.push({ kind: 'child', node: lit, text, owner: enclosingComponent(lit) })
        }
      }
    } else if (ts.isCallExpression(node) && ts.isPropertyAccessExpression(node.expression)) {
      const callee = node.expression
      if (ts.isIdentifier(callee.expression) && callee.expression.text === 'toast') {
        // Every literal in the call, not just the first argument: a message
        // written as `err instanceof Error ? err.message : 'Fallback text'`
        // hides prose one level down, and that is exactly where fallback
        // wording lives.
        const literals = []
        const dig = (n) => {
          // Stop at a translation call: the key inside it is already handled,
          // and descending would report the scanner's own output as a finding.
          if (isTranslationCall(n)) return
          if (ts.isStringLiteral(n) || ts.isTemplateExpression(n) ||
              ts.isNoSubstitutionTemplateLiteral(n)) literals.push(n)
          else ts.forEachChild(n, dig)
        }
        for (const arg of node.arguments) dig(arg)
        for (const lit of literals) {
          const raw = ts.isStringLiteral(lit) ? lit.text : lit.getText(sf).slice(1, -1)
          const text = normalize(raw)
          if (text && hasLetters(text) && !SKIP_VALUE.test(text)) {
            hits.push({ kind: 'toast', node: lit, text, owner: enclosingComponent(lit) })
          }
        }
      }
    }
    ts.forEachChild(node, visit)
  }
  visit(sf)
  return { sf, src, hits }
}

export function sourceFiles(root = 'src') {
  const out = []
  const walk = (dir) => {
    for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
      const p = path.join(dir, e.name)
      if (e.isDirectory()) { if (e.name !== 'locales') walk(p) }
      else if (/\.tsx$/.test(e.name) && !e.name.includes('.test.')) out.push(p)
    }
  }
  walk(root)
  return out.sort()
}

if (process.argv[1]?.endsWith('scan.mjs')) {
  let total = 0
  const perFile = []
  for (const f of sourceFiles()) {
    const { hits } = collect(f)
    const untranslated = hits.filter((h) => {
      // already wrapped? a t('…') call renders as a JsxExpression, never JsxText,
      // so anything we see here is literal.
      return true
    })
    if (untranslated.length) { perFile.push([f, untranslated.length]); total += untranslated.length }
  }
  console.log(`FILES=${perFile.length} STRINGS=${total}`)
  for (const [f, n] of perFile.sort((a, b) => b[1] - a[1]).slice(0, 25)) {
    console.log(String(n).padStart(4), f)
  }
}
