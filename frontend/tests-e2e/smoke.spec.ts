import { test, expect } from '@playwright/test'

test.describe('Smoke Tests', () => {
  test('homepage loads', async ({ page }) => {
    await page.goto('/')
    await expect(page).toHaveTitle(/Fund Watch/)
  })

  test('navigation works', async ({ page }) => {
    await page.goto('/')

    // Check navigation to portfolio page
    await page.click('[data-testid="nav-portfolio"]')
    await expect(page).toHaveURL(/\/portfolio/)

    // Check navigation to market page
    await page.click('[data-testid="nav-market"]')
    await expect(page).toHaveURL(/\/market/)

    // Check navigation to AI select page
    await page.click('[data-testid="nav-ai-select"]')
    await expect(page).toHaveURL(/\/ai-select/)

    // Check navigation to import page
    await page.click('[data-testid="nav-import"]')
    await expect(page).toHaveURL(/\/import/)

    // Check navigation to stock-funds page
    await page.click('[data-testid="nav-stock-funds"]')
    await expect(page).toHaveURL(/\/stock-funds/)

    // Check navigation back to overview
    await page.click('[data-testid="nav-overview"]')
    await expect(page).toHaveURL(/\/$/)
  })
})
