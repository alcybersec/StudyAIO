import { test, expect } from './fixtures'

const MINIMAL_PDF = `%PDF-1.4
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

test.describe('Upload', () => {
  test('upload page renders with drop zone', async ({ page }) => {
    await page.goto('/upload')
    await expect(page.getByText(/drop lecture files here|drop to upload/i)).toBeVisible({
      timeout: 10_000,
    })
  })

  test('upload a PDF file triggers pipeline', async ({ page }) => {
    await page.goto('/upload')
    await expect(page.getByText(/drop lecture files here/i)).toBeVisible({ timeout: 10_000 })

    // Find the file input (drop zone input, not the folder input)
    const fileInput = page.locator('input[type="file"]').first()
    await fileInput.setInputFiles({
      name: 'E2ETEST_week1.pdf',
      mimeType: 'application/pdf',
      buffer: Buffer.from(MINIMAL_PDF),
    })

    // Should see some feedback (uploading, processing, duplicate, or success)
    await expect(
      page.getByText(/uploading|processing|queued|duplicate|processed/i).first(),
    ).toBeVisible({ timeout: 15_000 })
  })

  test('upload page shows processing console', async ({ page }) => {
    await page.goto('/upload')
    await expect(page.getByText(/processing now/i)).toBeVisible({ timeout: 10_000 })
  })

  test('duplicate file upload is handled gracefully', async ({ page }) => {
    await page.goto('/upload')
    await expect(page.getByText(/drop lecture files here/i)).toBeVisible({ timeout: 10_000 })

    const fileInput = page.locator('input[type="file"]').first()

    // Upload twice
    await fileInput.setInputFiles({
      name: 'E2EDUP_week1.pdf',
      mimeType: 'application/pdf',
      buffer: Buffer.from(MINIMAL_PDF),
    })
    await page.waitForTimeout(2000)

    await fileInput.setInputFiles({
      name: 'E2EDUP_week1.pdf',
      mimeType: 'application/pdf',
      buffer: Buffer.from(MINIMAL_PDF),
    })

    // Should handle gracefully: duplicate badge appears, page doesn't crash
    await expect(
      page.getByText(/duplicate|processing|queued|processed/i).first(),
    ).toBeVisible({ timeout: 15_000 })
  })
})
