/**
 * Page-citation markers in generated summaries: `[p.3]`, or `[D2 p.1]` when
 * several source files were merged (GL#34).
 *
 * `remarkCitations` turns each marker into a `span` carrying `data-cite-*`
 * attributes, which the summary renderer draws as a chip. It only touches
 * plain text, so fenced code, inline code and link text keep their brackets.
 */

interface MdNode {
  type: string
  value?: string
  children?: MdNode[]
  data?: { hName?: string; hProperties?: Record<string, string> }
}

// Global flag: used with matchAll only, which clones the regex.
const MARKER = /\[(?:D(\d+)\s+)?p\.(\d+)\]/g

/** Node types whose text must stay literal. */
const LITERAL_PARENTS = new Set(['code', 'inlineCode', 'link', 'linkReference', 'definition', 'html'])

function splitText(node: MdNode): MdNode[] | null {
  const value = node.value ?? ''
  const matches = [...value.matchAll(MARKER)]
  if (matches.length === 0) return null

  const out: MdNode[] = []
  let last = 0
  for (const m of matches) {
    const start = m.index ?? 0
    if (start > last) out.push({ type: 'text', value: value.slice(last, start) })
    const props: Record<string, string> = { 'data-cite-page': m[2] }
    if (m[1]) props['data-cite-doc'] = m[1]
    out.push({
      type: 'citation',
      data: { hName: 'span', hProperties: props },
      children: [{ type: 'text', value: m[0] }],
    })
    last = start + m[0].length
  }
  if (last < value.length) out.push({ type: 'text', value: value.slice(last) })
  return out
}

function walk(node: MdNode): void {
  if (!node.children || LITERAL_PARENTS.has(node.type)) return
  const next: MdNode[] = []
  for (const child of node.children) {
    if (child.type === 'text') {
      next.push(...(splitText(child) ?? [child]))
    } else {
      walk(child)
      next.push(child)
    }
  }
  node.children = next
}

/** Remark plugin: wrap citation markers in chip-able spans. */
export function remarkCitations() {
  return (tree: MdNode) => walk(tree)
}
