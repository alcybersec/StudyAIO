import AxeBuilder from '@axe-core/playwright'
import { test, expect } from './fixtures'
import type { Page } from '@playwright/test'

const PAGES = ['/', '/study', '/upload', '/ask', '/settings', '/login']
const THEMES = ['dark', 'light'] as const

async function setTheme(page: Page, theme: (typeof THEMES)[number]): Promise<void> {
  await page.addInitScript((t) => {
    window.localStorage.setItem('studyaio-theme', t)
  }, theme)
}

async function runAxe(page: Page) {
  const results = await new AxeBuilder({ page })
    // Scan the app shell + page content; skip third-party canvas internals
    .analyze()
  return results.violations.filter(
    (v) => v.impact === 'serious' || v.impact === 'critical',
  )
}

for (const theme of THEMES) {
  test.describe(`A11y smoke (${theme} theme)`, () => {
    for (const path of PAGES) {
      test(`${path} has no serious/critical axe violations`, async ({ page }) => {
        await setTheme(page, theme)
        await page.goto(path)
        // networkidle never settles on pages with live SSE streams — wait for
        // the app shell + content to render instead.
        await expect(page.locator('#root > *').first()).toBeVisible({ timeout: 10_000 })
        await page.waitForTimeout(1500)

        const violations = await runAxe(page)
        if (violations.length > 0) {
          console.log(
            `axe violations on ${path} (${theme}):`,
            JSON.stringify(
              violations.map((v) => ({
                id: v.id,
                impact: v.impact,
                help: v.help,
                nodes: v.nodes.slice(0, 5).map((n) => n.html),
              })),
              null,
              2,
            ),
          )
        }
        expect(violations).toEqual([])
      })
    }
  })
}
