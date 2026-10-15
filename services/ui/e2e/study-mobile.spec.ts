import { test, expect } from './fixtures'
import type { Locator, Page } from '@playwright/test'

// UX-06 / GL#18: the Study hub tab bar must scroll inside its own container on
// narrow phones instead of widening the page, and every tab must stay reachable.

const VIEWPORTS = [
  { name: '375x667', width: 375, height: 667 },
  { name: '320x568', width: 320, height: 568 },
] as const
const THEMES = ['light', 'dark'] as const
const ROUTES = ['/study', '/study?tab=history', '/study?tab=exams'] as const
const TAB_NAMES = [/^plan/i, /^mastery/i, /^flashcards/i, /^timed/i, /^exams/i, /^history/i]

async function openStudy(page: Page, route: string, theme: (typeof THEMES)[number]) {
  await page.addInitScript((t) => {
    window.localStorage.setItem('studyaio-theme', t)
  }, theme)
  await page.goto(route)
  const tablist = page.getByRole('tablist').first()
  await expect(tablist).toBeVisible({ timeout: 10_000 })
  await expect
    .poll(() => page.evaluate(() => document.documentElement.classList.contains('dark')))
    .toBe(theme === 'dark')
  return tablist
}

/** Tab is fully inside the tablist's visible rect (not clipped by its scroll). */
async function expectWithinTablist(tab: Locator, tablist: Locator) {
  await expect
    .poll(async () => {
      const [t, l] = await Promise.all([tab.boundingBox(), tablist.boundingBox()])
      if (!t || !l) return false
      return t.x >= l.x - 1 && t.x + t.width <= l.x + l.width + 1
    })
    .toBe(true)
}

async function expectInViewport(page: Page, tab: Locator) {
  const vw = page.viewportSize()!.width
  await expect
    .poll(async () => {
      const b = await tab.boundingBox()
      return !!b && b.x >= -1 && b.x + b.width <= vw + 1
    })
    .toBe(true)
}

async function expectNoPageOverflow(page: Page) {
  const m = await page.evaluate(() => ({
    scroll: document.documentElement.scrollWidth,
    inner: window.innerWidth,
  }))
  expect(m.scroll).toBeLessThanOrEqual(m.inner)
}

for (const vp of VIEWPORTS) {
  for (const theme of THEMES) {
    test.describe(`Study hub tabs @ ${vp.name} (${theme})`, () => {
      test.use({ viewport: { width: vp.width, height: vp.height } })

      for (const route of ROUTES) {
        test(`${route}: no page-level horizontal overflow`, async ({ page }) => {
          await openStudy(page, route, theme)
          await expectNoPageOverflow(page)
        })
      }

      test('tablist scrolls inside itself when tabs do not fit', async ({ page }) => {
        const tablist = await openStudy(page, '/study', theme)
        const m = await tablist.evaluate((el) => {
          const tabs = Array.from(el.querySelectorAll<HTMLElement>('[role="tab"]'))
          return {
            scroll: el.scrollWidth,
            client: el.clientWidth,
            needed: tabs.reduce((n, t) => n + t.getBoundingClientRect().width, 0),
            overflowX: getComputedStyle(el).overflowX,
          }
        })
        expect(m.overflowX).toBe('auto')
        // If the tabs' natural widths exceed the bar, the bar itself must scroll.
        if (m.needed > m.client) expect(m.scroll).toBeGreaterThan(m.client)
        // 320px cannot fit six tabs; guard against the bar silently shrinking them.
        if (vp.width <= 320) expect(m.scroll).toBeGreaterThan(m.client)
        await expectNoPageOverflow(page)
      })

      test('all six tabs are reachable, selected, in view and >= 44px tall', async ({ page }) => {
        const tablist = await openStudy(page, '/study', theme)
        await expect(tablist.getByRole('tab')).toHaveCount(TAB_NAMES.length)
        for (const name of TAB_NAMES) {
          const tab = tablist.getByRole('tab', { name })
          await tab.click()
          await expect(tab).toHaveAttribute('aria-selected', 'true')
          await expectInViewport(page, tab)
          await expectWithinTablist(tab, tablist)
          const box = await tab.boundingBox()
          expect(box!.height).toBeGreaterThanOrEqual(44)
          await expectNoPageOverflow(page)
        }
      })

      test('deep link ?tab=history shows History fully inside the tablist', async ({ page }) => {
        const tablist = await openStudy(page, '/study?tab=history', theme)
        const tab = tablist.getByRole('tab', { name: /^history/i })
        await expect(tab).toHaveAttribute('aria-selected', 'true')
        await expectWithinTablist(tab, tablist)
        await expectInViewport(page, tab)
      })

      test('ArrowRight from Plan selects the next tab and keeps it in view', async ({ page }) => {
        const tablist = await openStudy(page, '/study', theme)
        const plan = tablist.getByRole('tab', { name: /^plan/i })
        await plan.focus()
        await expect(plan).toHaveAttribute('aria-selected', 'true')
        await page.keyboard.press('ArrowRight')
        const next = tablist.getByRole('tab', { name: /^mastery/i })
        await expect(next).toHaveAttribute('aria-selected', 'true')
        await expect(next).toBeFocused()
        await expectWithinTablist(next, tablist)
        await expectInViewport(page, next)
      })
    })
  }
}
