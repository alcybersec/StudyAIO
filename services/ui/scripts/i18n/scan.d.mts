/** Types for the i18n scanner, so the coverage guard can import it from TS. */
export interface I18nHit {
  kind: string
  text: string
  owner: { name: string | null; isComponent?: boolean; isClass?: boolean } | null
}
export function collect(file: string): { src: string; hits: I18nHit[] }
export function sourceFiles(root?: string): string[]
export function normalize(s: string): string
export function decode(s: string): string
