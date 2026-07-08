/**
 * Tiny event channel for opening the global command palette.
 *
 * Nav chrome (sidebar search affordance, shortcuts) calls
 * `openCommandPalette()`; the palette itself subscribes via
 * `onCommandPaletteOpen`. Avoids threading state through the layout tree.
 */
const EVENT = 'studyaio:command-palette'

export function openCommandPalette(): void {
  window.dispatchEvent(new CustomEvent(EVENT))
}

export function onCommandPaletteOpen(callback: () => void): () => void {
  window.addEventListener(EVENT, callback)
  return () => window.removeEventListener(EVENT, callback)
}

/**
 * Whether the palette's global-search Content section is available.
 * Flipped on with the GET /api/search endpoint; kept as a function so
 * tests can stub the flag off.
 */
export function isSearchAvailable(): boolean {
  return true
}
