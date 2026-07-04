import '@testing-library/jest-dom'

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
