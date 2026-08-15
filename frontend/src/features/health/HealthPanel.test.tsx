import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { ApiError } from '../../api/errors';
import type { HealthResponse } from '../../api/types';
import { createApiStub } from '../../test/apiStub';
import { HealthPanel } from './HealthPanel';

describe('HealthPanel', () => {
  it('shows loading and then the validated backend metadata', async () => {
    const api = createApiStub({
      getHealth: vi.fn().mockResolvedValue({
        status: 'ok',
        service: 'airmonitor-api',
        version: '2.0.0',
      }),
    });

    render(<HealthPanel api={api} />);

    expect(screen.getByText('Проверяем подключение…')).toBeInTheDocument();
    expect(await screen.findByText('Сервис доступен')).toBeInTheDocument();
    expect(screen.getByText('airmonitor-api · 2.0.0')).toBeInTheDocument();
  });

  it('shows a safe offline state and retries on demand', async () => {
    const getHealth = vi
      .fn()
      .mockRejectedValueOnce(new ApiError({ kind: 'network' }))
      .mockResolvedValueOnce({
        status: 'ok',
        service: 'airmonitor-api',
        version: '2.0.0',
      });
    const api = createApiStub({ getHealth });
    const user = userEvent.setup();

    render(<HealthPanel api={api} />);

    expect(await screen.findByText('Сервис недоступен')).toBeInTheDocument();
    expect(
      screen.getByText('Не удалось связаться с сервером.'),
    ).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Повторить проверку' }));

    expect(await screen.findByText('Сервис доступен')).toBeInTheDocument();
    expect(getHealth).toHaveBeenCalledTimes(2);
  });

  it('aborts the in-flight health request on unmount', () => {
    let observedSignal: AbortSignal | undefined;
    const api = createApiStub({
      getHealth: vi.fn((options) => {
        observedSignal = options?.signal;
        return new Promise<HealthResponse>(() => undefined);
      }),
    });

    const view = render(<HealthPanel api={api} />);
    view.unmount();

    expect(observedSignal?.aborted).toBe(true);
  });
});
