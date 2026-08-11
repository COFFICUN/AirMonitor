import { expect, test } from '@playwright/test';

test.skip(
  process.env.AIRMONITOR_COMPOSE_RECOVERY !== '1',
  'Runs only after a guarded disposable Compose restart.',
);

test('frontend reconnects to the restarted API and restores the selected device', async ({
  page,
}) => {
  const deviceId = Number(process.env.AIRMONITOR_SMOKE_DEVICE_ID ?? '1');
  await page.route('https://tile.openstreetmap.org/**', (route) => route.abort());
  await page.addInitScript((id) => {
    localStorage.setItem(
      'airmonitor.frontend.v2.device-id',
      JSON.stringify({ version: 1, deviceId: id }),
    );
  }, deviceId);

  await page.goto('/app/measurement');
  await expect(page.getByText('Система доступна')).toBeVisible();
  await expect(page.getByRole('link', { name: 'Compose smoke sensor' })).toBeVisible();
  await expect(
    page
      .getByRole('region', { name: 'Показания датчика' })
      .getByText('18,7', { exact: true }),
  ).toBeVisible({ timeout: 8_000 });
});
