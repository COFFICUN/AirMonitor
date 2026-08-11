import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { describe, expect, it, vi } from 'vitest';

import { App } from './App';
import { createApiStub } from './test/apiStub';

describe('application routing', () => {
  it.each([
    ['/', 'Измеряем воздух Алматы — точка за точкой'],
    ['/about', 'О проекте AirMonitor'],
    ['/participate', 'Как участвовать'],
    ['/methodology', 'Как читать измерения'],
    ['/login', 'Личный кабинет появится позже'],
  ])('renders public route %s', async (path, heading) => {
    render(
      <MemoryRouter initialEntries={[path]}>
        <App api={createApiStub()} />
      </MemoryRouter>,
    );
    expect(await screen.findByRole('heading', { level: 1, name: heading })).toBeVisible();
    expect(document.body.textContent).not.toMatch(/маршрут|трек|путь по городу/i);
  });

  it('does not call an authentication endpoint from the login page', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch');
    render(
      <MemoryRouter initialEntries={['/login']}>
        <App api={createApiStub()} />
      </MemoryRouter>,
    );
    await screen.findByRole('heading', { level: 1, name: 'Личный кабинет появится позже' });
    expect(fetchSpy).not.toHaveBeenCalled();
    fetchSpy.mockRestore();
  });

  it('renders a helpful not-found route', async () => {
    render(
      <MemoryRouter initialEntries={['/unknown-route']}>
        <App api={createApiStub()} />
      </MemoryRouter>,
    );
    expect(await screen.findByRole('heading', { level: 1, name: 'Страница не найдена' })).toBeVisible();
  });
});
