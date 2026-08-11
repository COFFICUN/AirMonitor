import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';

import { installMockBackend } from './fixtures';

async function expectNoBlockingViolations(page: Page) {
  const results = await new AxeBuilder({ page }).analyze();
  const blocking = results.violations.filter(({ impact }) => impact === 'serious' || impact === 'critical');
  expect(blocking).toEqual([]);
}

const darkPreferences = {
  version: 2,
  preferences: {
    density: 'comfortable',
    mapTilesEnabled: true,
    motion: 'system',
    pollingIntervalMs: 5_000,
    theme: 'dark',
    timeFormat: '24h',
  },
};

const publicRoutes = ['/', '/about', '/participate', '/methodology', '/login'] as const;

test('every public surface is readable in the light theme', async ({ page }) => {
  await page.addInitScript((preferences) => {
    window.localStorage.setItem('airmonitor.frontend.v2.preferences', JSON.stringify(preferences));
  }, { ...darkPreferences, preferences: { ...darkPreferences.preferences, theme: 'light' } });

  for (const path of publicRoutes) {
    await page.goto(path);
    await expect(page.locator('html')).toHaveAttribute('data-theme', 'light');
    await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
    await expectNoBlockingViolations(page);
  }
});

test('every public surface remains readable with the dark preference active', async ({ page }) => {
  await page.addInitScript((preferences) => {
    window.localStorage.setItem('airmonitor.frontend.v2.preferences', JSON.stringify(preferences));
  }, darkPreferences);

  for (const path of publicRoutes) {
    await page.goto(path);
    await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
    await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
    await expectNoBlockingViolations(page);
  }

  await page.setViewportSize({ width: 390, height: 844 });
  for (const path of publicRoutes) {
    await page.goto(path);
    const widths = await page.evaluate(() => ({ viewport: innerWidth, document: document.documentElement.scrollWidth }));
    expect(widths.document, path).toBeLessThanOrEqual(widths.viewport);
    await expectNoBlockingViolations(page);
  }
});

test('every participant surface is readable in both explicit themes', async ({ page }) => {
  await installMockBackend(page);
  await page.goto('/app/device');
  await page.getByLabel('ID существующего устройства').fill('42');
  await page.getByRole('button', { name: 'Подключить' }).click();
  await page.goto('/app/settings');
  await page.getByRole('combobox', { name: /Тема интерфейса/ }).selectOption('light');

  const participantRoutes = ['/app', '/app/device', '/app/measurement', '/app/data', '/app/map', '/app/settings'] as const;
  for (const path of participantRoutes) {
    await page.goto(path);
    await expect(page.locator('html')).toHaveAttribute('data-theme', 'light');
    await expect(page.locator('main').getByRole('heading', { level: 1 })).toBeVisible();
    await expectNoBlockingViolations(page);
  }

  await page.goto('/app/settings');
  await page.getByRole('combobox', { name: /Тема интерфейса/ }).selectOption('dark');
  for (const path of participantRoutes) {
    await page.goto(path);
    await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
    await expect(page.locator('main').getByRole('heading', { level: 1 })).toBeVisible();
    await expectNoBlockingViolations(page);
  }

  await page.setViewportSize({ width: 390, height: 844 });
  for (const path of participantRoutes) {
    await page.goto(path);
    const widths = await page.evaluate(() => ({ viewport: innerWidth, document: document.documentElement.scrollWidth }));
    expect(widths.document, path).toBeLessThanOrEqual(widths.viewport);
    await expectNoBlockingViolations(page);
  }
});

test('session cancellation dialog is keyboard reachable and axe-clean', async ({ context, page }) => {
  await installMockBackend(page);
  await context.grantPermissions(['geolocation'], { origin: 'http://127.0.0.1:5173' });
  await context.setGeolocation({ latitude: 43.238, longitude: 76.945 });
  await page.goto('/app/device');
  await page.getByLabel('ID существующего устройства').fill('42');
  await page.getByRole('button', { name: 'Подключить' }).click();
  await page.goto('/app/measurement');
  await page.getByRole('button', { name: 'Начать сессию' }).click();
  await page.getByRole('button', { name: 'Отменить' }).click();

  await expect(page.getByRole('alertdialog')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Вернуться' })).toBeFocused();
  await expectNoBlockingViolations(page);
  await page.keyboard.press('Escape');
  await expect(page.getByRole('alertdialog')).toHaveCount(0);
});
