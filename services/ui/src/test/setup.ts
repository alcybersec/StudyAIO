import '@testing-library/jest-dom'
import { configure } from '@testing-library/react'
import { vi } from 'vitest'

// The first test in each file pays the cold cost of its first render (module
// evaluation, JIT, jsdom layout). On a loaded shared runner that alone has
// outlasted waitFor's 1000 ms default and vitest's 5000 ms test timeout, so
// the first test of a file flaked while the rest passed. waitFor and findBy
// return as soon as the condition holds, so a longer ceiling costs nothing
// when green and only changes how long a genuine failure takes to report.
configure({ asyncUtilTimeout: 10_000 })
vi.setConfig({ testTimeout: 20_000 })

// i18n, so components calling `t()` render text rather than warning about a
// missing instance. English is the key set, so tests read as English.
import i18n, { i18nReady } from '../i18n'

// Russian is a lazily imported chunk. Load it once, up front, so a test that
// switches to it resolves from the in-memory bundle rather than racing a
// dynamic import against waitFor's timeout on a loaded runner.
await i18nReady
await i18n.loadLanguages('ru')

// Node's experimental localStorage global (undefined without --localstorage-file)
// shadows jsdom's; provide a real in-memory Storage for tests.
if (typeof window.localStorage === 'undefined' || window.localStorage == null) {
  let store: Record<string, string> = {}
  const stub: Storage = {
    getItem: (key: string) => (key in store ? store[key] : null),
    setItem: (key: string, value: string) => {
      store[key] = String(value)
    },
    removeItem: (key: string) => {
      delete store[key]
    },
    clear: () => {
      store = {}
    },
    key: (index: number) => Object.keys(store)[index] ?? null,
    get length() {
      return Object.keys(store).length
    },
  }
  Object.defineProperty(window, 'localStorage', { value: stub, configurable: true })
  Object.defineProperty(globalThis, 'localStorage', { value: stub, configurable: true })
}

// jsdom lacks matchMedia; useTheme resolves the system theme at import time.
// Tests that need specific behaviour override this (see useTheme.test.ts).
if (typeof window.matchMedia === 'undefined') {
  window.matchMedia = ((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addEventListener: () => {},
    removeEventListener: () => {},
    addListener: () => {},
    removeListener: () => {},
    dispatchEvent: () => false,
  })) as unknown as typeof window.matchMedia
}

// jsdom lacks these APIs; Radix popper-positioned components need them.
if (typeof window.ResizeObserver === 'undefined') {
  class ResizeObserverStub {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
  window.ResizeObserver = ResizeObserverStub as unknown as typeof ResizeObserver
}

if (typeof Element.prototype.scrollIntoView === 'undefined') {
  Element.prototype.scrollIntoView = () => {}
}
if (typeof Element.prototype.hasPointerCapture === 'undefined') {
  Element.prototype.hasPointerCapture = () => false
}
if (typeof Element.prototype.setPointerCapture === 'undefined') {
  Element.prototype.setPointerCapture = () => {}
}
if (typeof Element.prototype.releasePointerCapture === 'undefined') {
  Element.prototype.releasePointerCapture = () => {}
}
