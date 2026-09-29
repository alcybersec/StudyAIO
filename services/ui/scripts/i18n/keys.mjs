/** Every translation key in use, so the bundles can be checked against reality. */
import fs from 'node:fs'
import path from 'node:path'

const KEY = /\b(?:i18n\.)?t\(\s*(?:'((?:[^'\\]|\\.)*)'|"((?:[^"\\]|\\.)*)")/g
const keys = new Set()
const walk = (dir) => {
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, e.name)
    if (e.isDirectory()) { if (e.name !== 'locales') walk(p) }
    else if (/\.tsx?$/.test(e.name) && !e.name.includes('.test.') && p !== 'src/i18n/index.ts') {
      const src = fs.readFileSync(p, 'utf8')
      for (const m of src.matchAll(KEY)) {
        keys.add((m[1] ?? m[2]).replace(/\\'/g, "'").replace(/\\"/g, '"'))
      }
    }
  }
}
walk('src')
// Keys that arrive through a variable (t(label), t(hint), …) live in these tables.
const DYNAMIC = JSON.parse(fs.readFileSync('scripts/i18n/dynamic-keys.json', 'utf8'))
for (const k of DYNAMIC) keys.add(k)
const sorted = [...keys].filter((k) => !/^[a-z]+$/.test(k) || k.length > 3).sort()
if (process.argv.includes('--json')) console.log(JSON.stringify(sorted, null, 2))
else { console.log(`KEYS=${sorted.length}`); for (const k of sorted) console.log(k) }
