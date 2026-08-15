import { expect, test } from '@playwright/test';

test.skip(
  process.env.AIRMONITOR_COMPOSE_SMOKE !== '1',
  'Runs only against the guarded disposable Compose stack.',
);

test('real backend smoke covers device, geolocation, session, live data, history, chart, and map', async ({
  context,
  page,
}) => {
  await page.route('https://tile.openstreetmap.org/**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'image/svg+xml',
      body: '<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256"><rect width="256" height="256" fill="#e5eef3"/><path d="M0 64H256M0 128H256M0 192H256M64 0V256M128 0V256M192 0V256" stroke="#cbdce5" stroke-width="2"/></svg>',
    });
  });
  await context.grantPermissions(['geolocation']);
  await context.setGeolocation({ latitude: 43.238, longitude: 76.945 });
  await page.goto('/app/device');
  await expect(page.getByText('Система доступна')).toBeVisible();

  await page.getByLabel('UID нового устройства').fill('compose-smoke-ee08');
  await page.getByLabel('Название устройства').fill('Compose smoke sensor');
  await page.getByRole('button', { name: 'Зарегистрировать' }).click();
  await expect(page.getByText('compose-smoke-ee08')).toBeVisible();

  const storedDevice = await page.evaluate(() => {
    const raw = localStorage.getItem('airmonitor.frontend.v2.device-id');
    return raw === null ? null : (JSON.parse(raw) as { deviceId: number });
  });
  expect(storedDevice?.deviceId).toBeGreaterThan(0);
  const deviceId = storedDevice!.deviceId;

  await page.goto('/app/measurement');
  await page.getByRole('button', { name: 'Начать сессию' }).click();
  await expect(page.getByText(/Сессия №\d+ активна/)).toBeVisible();
  await page.evaluate(() => {
    (window as Window & { composeNoReload?: string }).composeNoReload = 'kept';
  });

  const measurementResult = await page.evaluate(async (id) => {
    const response = await fetch(`/api/v1/devices/${id}/measurements`, {
      method: 'POST',
      headers: {
        Accept: 'application/json',
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        measured_at: new Date().toISOString(),
        source_message_id: 'compose-smoke-measurement-1',
        temperature: 24.6,
        humidity: 43.2,
        pm1: 5.1,
        pm25: 18.7,
        pm10: 27.3,
        latitude: 43.238,
        longitude: 76.945,
        is_valid: true,
        validation_note: null,
      }),
    });
    return { status: response.status, body: await response.json() };
  }, deviceId);
  expect(measurementResult.status).toBe(201);

  await expect(
    page
      .getByRole('region', { name: 'Показания датчика' })
      .getByText('18,7', { exact: true }),
  ).toBeVisible({ timeout: 8_000 });
  expect(
    await page.evaluate(
      () => (window as Window & { composeNoReload?: string }).composeNoReload,
    ),
  ).toBe('kept');

  await page.getByRole('button', { name: 'Завершить' }).click();
  await expect(page.getByText('Нет активной сессии')).toBeVisible();
  await page.goto('/app/sessions');
  await expect(page.getByRole('button', { name: /Сессия №\d+/ })).toBeVisible();
  await page.getByRole('link', { name: 'Открыть данные' }).click();
  await expect(page.getByRole('cell', { name: '18,7' })).toBeVisible();
  await expect(page.getByRole('img', { name: /PM2.5/ })).toBeVisible();
  await page.getByRole('link', { name: 'Карта', exact: true }).click();
  await expect(
    page.getByRole('region', { name: 'Интерактивная карта измерительных точек' }),
  ).toBeVisible();

  await page.reload();
  await expect(page.getByRole('link', { name: 'Compose smoke sensor' })).toBeVisible();
  await expect(page.getByText('Система доступна')).toBeVisible();
});
