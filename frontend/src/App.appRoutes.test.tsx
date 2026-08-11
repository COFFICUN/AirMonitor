import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router';
import { beforeEach, describe, expect, it } from 'vitest';

import { App } from './App';
import { createApiStub } from './test/apiStub';
import { PREFERENCES_STORAGE_KEY } from './storage/preferencesStorage';

const api = createApiStub({
  getHealth: async () => ({ status: 'ok', service: 'airmonitor-api', version: '2.0.0' }),
});

beforeEach(() => localStorage.clear());

describe('participant application routes', () => {
  it.each([
    ['/app', 'Добрый день!'],
    ['/app/measurement', 'Новое измерение'],
    ['/app/sessions', 'Мои сессии'],
    ['/app/map', 'Карта точек'],
    ['/app/data', 'Данные'],
    ['/app/device', 'Моё устройство'],
    ['/app/settings', 'Настройки'],
  ])('renders %s inside the participant shell', async (path, heading) => {
    render(<MemoryRouter initialEntries={[path]}><App api={api} /></MemoryRouter>);
    expect(await screen.findByRole('heading', { level: 1, name: heading })).toBeVisible();
    expect(screen.getByRole('navigation', { name: 'Разделы приложения' })).toBeVisible();
    expect(screen.getByText('Участник', { selector: '.participant-chip' })).toBeVisible();
    expect(document.body.textContent).not.toMatch(/маршрут|трек|путь по городу/i);
  });

  it('persists and applies reduced-motion and compact-density preferences', async () => {
    const user = userEvent.setup();
    render(<MemoryRouter initialEntries={['/app/settings']}><App api={api} /></MemoryRouter>);
    await screen.findByRole('heading', { level: 1, name: 'Настройки' });
    await user.selectOptions(screen.getByRole('combobox', { name: /Тема интерфейса/ }), 'dark');
    await user.selectOptions(screen.getByRole('combobox', { name: /Плотность интерфейса/ }), 'compact');
    await user.selectOptions(screen.getByRole('combobox', { name: /Анимация интерфейса/ }), 'reduced');

    expect(document.documentElement.dataset.theme).toBe('dark');
    expect(document.documentElement.dataset.density).toBe('compact');
    expect(document.documentElement.dataset.motion).toBe('reduced');
    expect(localStorage.getItem(PREFERENCES_STORAGE_KEY)).toContain('reduced');
  });
});
