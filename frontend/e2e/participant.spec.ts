import { expect, test, type Page } from '@playwright/test';

import { installMockBackend, MEASUREMENT_CURSOR, SESSION_CURSOR } from './fixtures';

async function selectDevice(page: Page) {
  await page.goto('/app/device');
  await page.getByLabel('ID существующего устройства').fill('42');
  await page.getByRole('button', { name: 'Подключить' }).click();
  await expect(page.getByText('sensor-42')).toBeVisible();
}

test('health, device selection, persistence, clearing, and registration work', async ({ page }) => {
  await installMockBackend(page);
  await selectDevice(page);
  await expect(page.getByText('Система доступна')).toBeVisible();
  await page.reload();
  await expect(page.getByText('sensor-42')).toBeVisible();

  await page.getByRole('button', { name: 'Очистить выбор' }).click();
  await page.getByLabel('UID нового устройства').fill('sensor-new');
  await page.getByLabel('Название устройства').fill('Мобильный датчик');
  await page.getByRole('button', { name: 'Зарегистрировать' }).click();
  await expect(page.getByText('sensor-new')).toBeVisible();
  await expect(page.getByLabel('Выбранный датчик').getByText('Мобильный датчик')).toBeVisible();
});

test('one-shot geolocation starts a session, live data changes without reload, and completion works', async ({ context, page }) => {
  const state = await installMockBackend(page);
  await context.grantPermissions(['geolocation'], { origin: 'http://127.0.0.1:5173' });
  await context.setGeolocation({ latitude: 43.238, longitude: 76.945 });
  await selectDevice(page);
  await page.goto('/app/measurement');

  await page.getByRole('button', { name: 'Начать сессию' }).click();
  await expect(page.getByText('Сессия №12 активна')).toBeVisible();
  await expect(page.getByLabel('Длительность активной сессии')).toBeVisible();
  expect(state.sessionStartBodies).toEqual([{ latitude: 43.238, longitude: 76.945 }]);

  await page.evaluate(() => { (window as Window & { noReload?: string }).noReload = 'kept'; });
  const readsBeforeUpdate = state.liveReadCount;
  await expect.poll(() => state.liveReadCount, { timeout: 8_000 }).toBeGreaterThan(readsBeforeUpdate);
  await expect(page.getByText('8,8', { exact: true })).toBeVisible({ timeout: 8_000 });
  expect(await page.evaluate(() => (window as Window & { noReload?: string }).noReload)).toBe('kept');

  await page.getByRole('button', { name: 'Завершить' }).click();
  await expect(page.getByText('Нет активной сессии')).toBeVisible();
});

test('geolocation denial is explicit, safe, and does not call the session API', async ({ page }) => {
  const state = await installMockBackend(page);
  await page.addInitScript(() => {
    Object.defineProperty(navigator, 'geolocation', { configurable: true, value: { getCurrentPosition: (_success: PositionCallback, failure?: PositionErrorCallback) => failure?.({ code: 1, message: 'raw permission detail', PERMISSION_DENIED: 1, POSITION_UNAVAILABLE: 2, TIMEOUT: 3 }) } });
  });
  await selectDevice(page);
  await page.goto('/app/measurement');
  await page.getByRole('button', { name: 'Начать сессию' }).click();

  await expect(page.getByText('Доступ к геопозиции запрещён. Разрешите его в настройках браузера.')).toBeVisible();
  expect(state.sessionStartBodies).toHaveLength(0);
  await expect(page.getByText('raw permission detail')).toHaveCount(0);
});

test('opaque cursors drive sessions, selected data, chart, table, and measurement-point map', async ({ page }) => {
  const state = await installMockBackend(page);
  await selectDevice(page);
  await page.goto('/app/sessions');

  await expect(page.getByRole('button', { name: /Сессия №11/ })).toBeVisible();
  await page.getByRole('button', { name: 'Загрузить ещё сессии' }).click();
  await expect(page.getByRole('button', { name: /Сессия №10/ })).toBeVisible();
  expect(state.seenSessionCursors).toEqual([SESSION_CURSOR]);

  await page.getByRole('button', { name: /Сессия №10/ }).click();
  await page.getByRole('link', { name: 'Открыть данные' }).click();
  await expect(page.getByRole('img', { name: /PM2.5/ })).toBeVisible();
  await expect(page.getByRole('cell', { name: '201' })).toBeVisible();
  await page.getByLabel('Метрика для статистики').selectOption('temperature');
  await expect(page.getByRole('heading', { name: 'Статистика Температура' })).toBeVisible();
  await page.getByRole('button', { name: 'Загрузить ещё измерения' }).click();
  await expect(page.getByRole('cell', { name: '200' })).toBeVisible();
  expect(state.seenMeasurementCursors).toEqual([MEASUREMENT_CURSOR]);

  await page.getByRole('link', { name: 'Карта', exact: true }).click();
  await expect(page.getByRole('region', { name: 'Интерактивная карта измерительных точек' })).toBeVisible();
  await expect(page.getByText('точки на карте', { exact: true })).toBeVisible();
  await expect(page.getByRole('complementary').getByText('Точка сессии №10')).toBeVisible();
});

test('settings persist and disabling tiles keeps the dashboard and map useful', async ({ page }) => {
  await installMockBackend(page);
  await selectDevice(page);
  await page.goto('/app/settings');
  await page.getByLabel(/Тема интерфейса/).selectOption('dark');
  await page.getByLabel(/Плотность интерфейса/).selectOption('compact');
  await page.getByLabel(/Анимация интерфейса/).selectOption('reduced');
  await page.getByLabel('Загружать OpenStreetMap').uncheck();
  await page.reload();

  await expect(page.getByLabel(/Тема интерфейса/)).toHaveValue('dark');
  await expect(page.getByLabel(/Плотность интерфейса/)).toHaveValue('compact');
  await page.goto('/app/map');
  await expect(page.getByText('Подложка карты отключена')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Включить подложку' })).toBeVisible();
});

test('every participant route is reachable through visible navigation', async ({ page }) => {
  await installMockBackend(page);
  await page.goto('/app');
  for (const [name, heading] of [['Новое измерение', 'Новое измерение'], ['Мои сессии', 'Мои сессии'], ['Карта', 'Карта точек'], ['Данные', 'Данные'], ['Моё устройство', 'Моё устройство'], ['Настройки', 'Настройки']] as const) {
    await page.getByRole('navigation', { name: 'Разделы приложения' }).getByRole('link', { name }).click();
    await expect(page.getByRole('heading', { level: 1, name: heading })).toBeVisible();
  }
});

test('malformed server failures stay sanitized and the narrow app does not overflow', async ({ page }) => {
  await installMockBackend(page, { malformedDeviceId: 500 });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/app/device');
  await page.getByLabel('ID существующего устройства').fill('500');
  await page.getByRole('button', { name: 'Подключить' }).click();
  await expect(page.getByRole('alert')).toContainText('Не удалось подключить устройство.');
  await expect(page.getByText('sensitive-stack-value')).toHaveCount(0);
  const widths = await page.evaluate(() => ({ viewport: innerWidth, document: document.documentElement.scrollWidth }));
  expect(widths.document).toBeLessThanOrEqual(widths.viewport);
  await expect(page.getByRole('navigation', { name: 'Мобильная навигация' })).toBeVisible();
});

test('participant layout stays contained at every required acceptance viewport', async ({ page }) => {
  await installMockBackend(page);
  await page.addInitScript(() => {
    localStorage.setItem('airmonitor.frontend.v2.device-id', JSON.stringify({ version: 1, deviceId: 42 }));
  });

  for (const viewport of [
    { width: 360, height: 800 },
    { width: 390, height: 844 },
    { width: 768, height: 1024 },
    { width: 1280, height: 800 },
    { width: 1440, height: 900 },
    { width: 1920, height: 1080 },
  ]) {
    await page.setViewportSize(viewport);
    await page.goto('/app');
    await expect(page.getByRole('heading', { level: 1, name: 'Добрый день!' })).toBeVisible();
    const widths = await page.evaluate(() => ({ viewport: innerWidth, document: document.documentElement.scrollWidth }));
    expect(widths.document, `${viewport.width}x${viewport.height}`).toBeLessThanOrEqual(widths.viewport);
    if (viewport.width <= 900) await expect(page.getByRole('navigation', { name: 'Мобильная навигация' })).toBeVisible();
    else await expect(page.getByRole('navigation', { name: 'Разделы приложения' })).toBeVisible();
  }
});

test('collapsed sidebar keeps the brand and toggle fully inside its bounds', async ({ page }) => {
  await installMockBackend(page);
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto('/app');

  const sidebar = page.locator('.app-sidebar');
  const brandMark = sidebar.locator('.brand__mark');
  const toggle = page.getByRole('button', { name: 'Свернуть меню' });
  await toggle.click();
  await expect(sidebar).toHaveCSS('width', '84px');

  const [sidebarBox, brandBox, toggleBox] = await Promise.all([
    sidebar.boundingBox(),
    brandMark.boundingBox(),
    page.getByRole('button', { name: 'Развернуть меню' }).boundingBox(),
  ]);
  expect(sidebarBox).not.toBeNull();
  expect(brandBox).not.toBeNull();
  expect(toggleBox).not.toBeNull();

  expect(toggleBox!.x).toBeGreaterThanOrEqual(sidebarBox!.x);
  expect(toggleBox!.x + toggleBox!.width).toBeLessThanOrEqual(sidebarBox!.x + sidebarBox!.width);
  expect(brandBox!.y + brandBox!.height).toBeLessThanOrEqual(toggleBox!.y);
});
