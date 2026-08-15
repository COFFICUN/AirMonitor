import { expect, test } from '@playwright/test';

function isBackendRequest(url: string): boolean {
  const path = new URL(url).pathname;
  return path === '/health' || path.startsWith('/api/v1/');
}

test('landing explains the real project and leads into the participant app', async ({ page }) => {
  const apiRequests: string[] = [];
  page.on('request', (request) => {
    if (isBackendRequest(request.url())) apiRequests.push(request.url());
  });

  await page.goto('/');

  await expect(page.getByRole('heading', { level: 1, name: 'Измеряем воздух Алматы — точка за точкой' })).toBeVisible();
  await expect(page.getByRole('img', { name: /Айри/ })).toBeVisible();
  await expect(page.getByText('Одна сессия — одна географическая точка')).toBeVisible();
  await expect(page.getByRole('link', { name: 'Начать измерение' })).toHaveAttribute('href', '/app/measurement');
  await expect(page.locator('main')).not.toContainText(/маршрут|трек|путь по городу/i);
  expect(apiRequests).toEqual([]);
});

for (const [path, heading] of [
  ['/about', 'О проекте AirMonitor'],
  ['/participate', 'Как участвовать'],
  ['/methodology', 'Как читать измерения'],
  ['/login', 'Личный кабинет появится позже'],
] as const) {
  test(`public route ${path} renders its honest content`, async ({ page }) => {
    await page.goto(path);
    await expect(page.getByRole('heading', { level: 1, name: heading })).toBeVisible();
    await expect(page.getByRole('navigation', { name: 'Основная навигация' })).toBeVisible();
    await expect(page.locator('main')).not.toContainText(/маршрут|трек|путь по городу/i);
  });
}

test('future login cannot submit, store credentials, or imitate authentication', async ({ page }) => {
  const requests: string[] = [];
  page.on('request', (request) => requests.push(request.url()));
  await page.goto('/login');

  await expect(page.getByLabel('Электронная почта')).toBeDisabled();
  await expect(page.getByLabel('Пароль')).toBeDisabled();
  await expect(page.getByRole('button', { name: 'Войти' })).toBeDisabled();
  expect(await page.evaluate(() => Object.keys(localStorage))).toEqual([]);
  expect(requests.filter(isBackendRequest)).toEqual([]);
});

test('public navigation and narrow layout stay usable', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/');
  await page.getByRole('button', { name: 'Открыть меню' }).click();
  await page.getByRole('link', { name: 'Методика' }).click();
  await expect(page).toHaveURL(/\/methodology$/);
  const widths = await page.evaluate(() => ({ viewport: innerWidth, document: document.documentElement.scrollWidth }));
  expect(widths.document).toBeLessThanOrEqual(widths.viewport);
});

test('the interface uses the readable Onest type family site-wide', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
  await page.evaluate(() => document.fonts.ready);

  const families = await page.evaluate(() => ({
    body: getComputedStyle(document.body).fontFamily,
    heading: getComputedStyle(document.querySelector('h1')!).fontFamily,
  }));

  expect(families.body).toContain('Onest');
  expect(families.heading).toContain('Onest');
  expect(await page.evaluate(() => document.fonts.check('16px Onest'))).toBe(true);
});
