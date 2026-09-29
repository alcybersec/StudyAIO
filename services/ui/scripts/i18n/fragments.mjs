/** Report JSX elements whose text was split across expressions. */
import ts from 'typescript'
import fs from 'node:fs'
import { sourceFiles } from './scan.mjs'

for (const file of sourceFiles()) {
  const src = fs.readFileSync(file, 'utf8')
  const sf = ts.createSourceFile(file, src, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX)
  const out = []
  const visit = (n) => {
    if (ts.isJsxElement(n)) {
      const kids = n.children
      const tCalls = kids.filter((c) => ts.isJsxExpression(c) && /^\{i18n\.t\(|^\{t\(/.test(c.getText(sf)))
      const others = kids.filter((c) => ts.isJsxExpression(c) && !/^\{i18n\.t\(|^\{t\(/.test(c.getText(sf)) && c.expression)
      if (tCalls.length && (tCalls.length > 1 || others.length)) {
        const line = sf.getLineAndCharacterOfPosition(n.getStart(sf)).line + 1
        out.push(`${line}: ${n.getText(sf).replace(/\s+/g, ' ').slice(0, 220)}`)
      }
    }
    ts.forEachChild(n, visit)
  }
  visit(sf)
  if (out.length) {
    console.log(`\n=== ${file}`)
    for (const o of out) console.log('  ' + o)
  }
}
