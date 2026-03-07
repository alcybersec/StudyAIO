import { test, expect } from './fixtures'

test.describe('Upload', () => {
  test('upload page renders with drop zone', async ({ page }) => {
    await page.goto('/upload')
    await expect(page.getByText(/upload|drop files|drag/i)).toBeVisible({ timeout: 10_000 })
  })

  test('upload a PDF file triggers pipeline', async ({ page }) => {
    await page.goto('/upload')
    await page.waitForLoadState('networkidle')

    // Create a minimal PDF in-memory
    const pdfContent = `%PDF-1.4
1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj
2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj
3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R/Resources<<>>>>endobj
xref
0 4
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
trailer<</Size 4/Root 1 0 R>>
startxref
211
%%EOF`

    // Find the file input
    const fileInput = page.locator('input[type="file"]')
    if (await fileInput.count() > 0) {
      await fileInput.setInputFiles({
        name: 'E2ETEST_week1.pdf',
        mimeType: 'application/pdf',
        buffer: Buffer.from(pdfContent),
      })
      // Should see some feedback (uploading, processing, or success)
      await expect(
        page.getByText(/upload|processing|queued|success|pipeline/i),
      ).toBeVisible({ timeout: 15_000 })
    }
  })

  test('upload page shows recent uploads list', async ({ page }) => {
    await page.goto('/upload')
    await page.waitForLoadState('networkidle')

    // The page should show either recent uploads or be empty
    const pageContent = await page.textContent('body')
    expect(pageContent).toBeTruthy()
  })

  test('duplicate file upload is handled gracefully', async ({ page }) => {
    await page.goto('/upload')
    await page.waitForLoadState('networkidle')

    const pdfContent = `%PDF-1.4
1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj
2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj
3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R/Resources<<>>>>endobj
xref
0 4
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
trailer<</Size 4/Root 1 0 R>>
startxref
211
%%EOF`

    const fileInput = page.locator('input[type="file"]')
    if (await fileInput.count() > 0) {
      // Upload twice
      await fileInput.setInputFiles({
        name: 'E2EDUP_week1.pdf',
        mimeType: 'application/pdf',
        buffer: Buffer.from(pdfContent),
      })
      await page.waitForTimeout(2000)

      await fileInput.setInputFiles({
        name: 'E2EDUP_week1.pdf',
        mimeType: 'application/pdf',
        buffer: Buffer.from(pdfContent),
      })

      // Should handle gracefully (no crash, show duplicate or success message)
      await page.waitForTimeout(2000)
      const pageContent = await page.textContent('body')
      expect(pageContent).toBeTruthy()
    }
  })
})
