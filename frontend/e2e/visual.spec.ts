import { expect, test } from '@playwright/test';
import path from 'node:path';

import { installMockBackend } from './fixtures';

test.skip(process.env.AIRMONITOR_VISUAL_CAPTURE !== '1', 'Creates the reviewed screenshot set on demand.');

const outputRoot = path.resolve('test-results', 'visual');

async function settle(page: import('@playwright/test').Page) {
  await page.locator('.route-loading').waitFor({ state: 'detached' });
  await page.evaluate(() => document.fonts.ready);
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.waitForTimeout(150);
}

async function capture(page: import('@playwright/test').Page, name: string, fullPage = false) {
  await settle(page);
  await page.screenshot({ path: path.join(outputRoot, name), fullPage, animations: 'disabled' });
}

test('capture reviewed public and participant surfaces', async ({ context, page }) => {
  await installMockBackend(page);
  await context.grantPermissions(['geolocation'], { origin: 'http://127.0.0.1:5173' });
  await context.setGeolocation({ latitude: 43.238, longitude: 76.945 });

  for (const [route, file] of [['/', '01-landing-desktop.png'], ['/about', '02-about.png'], ['/participate', '03-participate.png'], ['/methodology', '04-methodology.png'], ['/login', '05-login.png']] as const) {
    await page.goto(route);
    await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
    await capture(page, file, true);
  }

  await page.goto('/app/device');
  await page.getByLabel('ID существующего устройства').fill('42');
  await page.getByRole('button', { name: 'Подключить' }).click();
  await expect(page.getByText('sensor-42')).toBeVisible();
  await capture(page, '06-device.png', true);

  await page.goto('/app');
  await expect(page.getByRole('heading', { level: 1, name: 'Добрый день!' })).toBeVisible();
  await capture(page, '07-overview.png', true);

  await page.goto('/app/measurement');
  await page.getByRole('button', { name: 'Начать сессию' }).click();
  await expect(page.getByText('Сессия №12 активна')).toBeVisible();
  await capture(page, '08-active-measurement.png', true);

  await page.goto('/app/sessions');
  await page.getByRole('button', { name: 'Загрузить ещё сессии' }).click();
  await capture(page, '09-sessions.png', true);

  await page.goto('/app/data');
  await expect(page.getByRole('table')).toBeVisible();
  await capture(page, '10-data.png', true);

  await page.goto('/app/map');
  await expect(page.getByRole('region', { name: 'Интерактивная карта измерительных точек' })).toBeVisible();
  await capture(page, '11-map.png', true);

  await page.goto('/app/settings');
  await capture(page, '12-settings.png', true);
  await page.getByRole('combobox', { name: /Тема интерфейса/ }).selectOption('dark');
  await capture(page, '15-settings-dark.png', true);

  for (const [route, file] of [['/', '16-landing-dark.png'], ['/about', '17-about-dark.png'], ['/participate', '18-participate-dark.png'], ['/methodology', '19-methodology-dark.png'], ['/login', '20-login-dark.png']] as const) {
    await page.goto(route);
    await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
    await capture(page, file, true);
  }

  await page.goto('/app/settings');
  await page.getByRole('combobox', { name: /Тема интерфейса/ }).selectOption('system');

  await page.setViewportSize({ width: 360, height: 800 });
  await page.goto('/');
  await capture(page, '13-landing-mobile.png', true);
  await page.goto('/app');
  await capture(page, '14-overview-mobile.png', true);
});

