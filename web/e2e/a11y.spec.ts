import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';
import { mockApi } from './mockApi';

const WCAG_AA = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'];

/** Report serious/critical WCAG 2.1 AA violations (T-36, NFR-03). */
async function audit(page: import('@playwright/test').Page) {
  const results = await new AxeBuilder({ page })
    .withTags(WCAG_AA)
    // The WebGL canvas and third-party map controls are covered by the globe's own
    // ARIA label and keyboard handling (T-45).
    .exclude('.maplibregl-canvas-container')
    .exclude('.maplibregl-ctrl-attrib')
    .analyze();
  return results.violations.filter((v) => ['serious', 'critical'].includes(v.impact ?? ''));
}

test.beforeEach(async ({ page }) => {
  await mockApi(page);
});

test('main view passes axe WCAG 2.1 AA with an area selected', async ({ page }) => {
  await page.goto('/?region=id-sumsel');
  await expect(page.locator('.calendar__cell').first()).toBeVisible();
  await expect(page.locator('#summary .kpi__value').first()).toBeVisible();
  expect(await audit(page)).toEqual([]);
});

test('anomaly view and methodology page pass axe WCAG 2.1 AA', async ({ page }) => {
  await page.goto('/?region=id-sumsel&view=anomaly');
  await expect(page.locator('.calendar__cell').first()).toBeVisible();
  expect(await audit(page)).toEqual([]);
  await page.getByRole('button', { name: 'Methodology' }).click();
  await expect(page.getByRole('heading', { level: 2, name: 'Methodology' })).toBeVisible();
  expect(await audit(page)).toEqual([]);
});

test('keyboard only: choose a region, open a month, read its tooltip', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('button', { name: /South Sumatra/ }).focus();
  await page.keyboard.press('Enter');
  const cell = page.getByRole('gridcell', { name: /^September 2016/ });
  await expect(cell).toBeVisible();
  await cell.focus();
  await expect(page.getByRole('tooltip')).toContainText('September 2016');
  await page.keyboard.press('Enter');
  await expect(page.locator('.globe__month')).toHaveText('September 2016');
  await expect(cell).toHaveAttribute('aria-selected', 'true');
});

test('every interactive control is reachable with Tab and shows a focus ring', async ({ page }) => {
  await page.goto('/?region=id-sumsel');
  await expect(page.locator('.calendar__cell').first()).toBeVisible();
  const seen = new Set<string>();
  for (let i = 0; i < 60; i++) {
    await page.keyboard.press('Tab');
    const info = await page.evaluate(() => {
      const el = document.activeElement as HTMLElement | null;
      if (!el || el === document.body) return null;
      const style = getComputedStyle(el);
      return {
        name:
          el.getAttribute('aria-label') ||
          el.textContent?.trim().slice(0, 30) ||
          `${el.tagName.toLowerCase()}#${el.id}`,
        outline: style.outlineStyle !== 'none' && style.outlineWidth !== '0px',
      };
    });
    if (!info) continue;
    expect(info.outline, `focus ring on ${info.name}`).toBe(true);
    seen.add(info.name);
  }
  // header tabs, globe tools, the globe itself and time controls are all in the tab order
  for (const name of ['Methodology', 'Polygon', 'Play']) {
    expect(
      [...seen].some((s) => s.includes(name)),
      name,
    ).toBe(true);
  }
  expect([...seen].some((s) => s.startsWith('Interactive hotspot globe'))).toBe(true);
});
