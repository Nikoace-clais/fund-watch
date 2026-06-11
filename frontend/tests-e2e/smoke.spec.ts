import { test, expect } from '@playwright/test';

test.describe('Smoke Tests', () => {
  test('homepage loads', async ({ page }) => {
    await page.goto('/');
    await expect(page).toHaveTitle(/Fund Watch/);
  });

  test('navigation works', async ({ page }) => {
    await page.goto('/');
    
    // Check navigation to funds page
    await page.click('[data-testid="nav-funds"]');
    await expect(page).toHaveURL(/\/funds/);
    
    // Check navigation to portfolio page
    await page.click('[data-testid="nav-portfolio"]');
    await expect(page).toHaveURL(/\/portfolio/);
  });
});
