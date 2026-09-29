/** Types for the .ts scanner, so the coverage guard can import it. */
export interface TsHit {
  kind: string
  text: string
}
export function collectTs(file: string): { src: string; hits: TsHit[] }
export function tsFiles(root?: string): string[]
