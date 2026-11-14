import { expect, test } from '@playwright/test';
import { mockApi } from './mockApi';

test.beforeEach(async ({ page }) => {
  await mockApi(page);
});

test('app shell renders', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('heading', { level: 1, name: 'FireCal' })).toBeVisible();
  await expect(page.getByText('NRT data not final')).toBeVisible();
});

test('main flow: globe → region → calendar → CSV', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('application', { name: /Interactive hotspot globe/ })).toBeVisible();
  await page.getByRole('button', { name: /South Sumatra/ }).click();
  await expect(page.locator('.aoi-summary')).toContainText('South Sumatra, Indonesia');
  await expect(page.getByRole('gridcell', { name: /^September 2016/ })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'November 2026 vs usual' })).toBeVisible();
  const [download] = await Promise.all([
    page.waitForEvent('download'),
    page.getByRole('button', { name: 'Monthly CSV' }).click(),
  ]);
  expect(download.suggestedFilename()).toBe('firecal_monthly_2001-01_2026-11.csv');
  await expect(page).toHaveURL(/region=id-sumsel/);
});
