import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { ApiError } from '../../api/errors';
import type { AirMonitorApi, SessionResponse } from '../../api/types';
import { GeolocationFailure } from '../../geolocation/geolocation';
import { createApiStub } from '../../test/apiStub';
import { SessionPanel } from './SessionPanel';
import { useActiveSession } from './useActiveSession';

const activeSession: SessionResponse = {
  id: 7,
  device_id: 42,
  status: 'active',
  started_at: '2026-08-04T06:00:00Z',
  ended_at: null,
  latitude: 51.128,
  longitude: 71.431,
  sample_count: 0,
  created_at: '2026-08-04T06:00:00Z',
};

function noActiveSession() {
  return new ApiError({
    kind: 'http',
    status: 404,
    code: 'active_session_not_found',
  });
}

function Harness({
  api,
  requestLocation = vi.fn().mockResolvedValue({
    latitude: 51.128,
    longitude: 71.431,
  }),
  deviceId = 42,
  deviceActive = true,
  onSessionChanged,
}: {
  readonly api: AirMonitorApi;
  readonly requestLocation?: () => Promise<{
    readonly latitude: number;
    readonly longitude: number;
  }>;
  readonly deviceId?: number | null;
  readonly deviceActive?: boolean;
  readonly onSessionChanged?: () => void;
}) {
  const session = useActiveSession(api, deviceId, {
    requestLocation,
    onSessionChanged,
  });
  return <SessionPanel session={session} deviceActive={deviceActive} />;
}

describe('SessionPanel', () => {
  it('loads the active state without requesting geolocation on render', async () => {
    const requestLocation = vi.fn();
    const getActiveSession = vi.fn().mockRejectedValue(noActiveSession());

    render(
      <Harness
        api={createApiStub({ getActiveSession })}
        requestLocation={requestLocation}
      />,
    );

    expect(await screen.findByText('Нет активной сессии')).toBeInTheDocument();
    expect(getActiveSession).toHaveBeenCalledWith(42, expect.any(Object));
    expect(requestLocation).not.toHaveBeenCalled();
  });

  it('requests one position only when the user starts a session', async () => {
    const requestLocation = vi.fn().mockResolvedValue({
      latitude: 51.128,
      longitude: 71.431,
    });
    const startSession = vi.fn().mockResolvedValue(activeSession);
    const onSessionChanged = vi.fn();
    const user = userEvent.setup();

    render(
      <Harness
        api={createApiStub({
          getActiveSession: vi.fn().mockRejectedValue(noActiveSession()),
          startSession,
        })}
        requestLocation={requestLocation}
        onSessionChanged={onSessionChanged}
      />,
    );
    await screen.findByText('Нет активной сессии');
    await user.click(screen.getByRole('button', { name: 'Начать сессию' }));

    expect(await screen.findByText('Сессия №7 активна')).toBeInTheDocument();
    expect(requestLocation).toHaveBeenCalledOnce();
    expect(startSession).toHaveBeenCalledWith(
      42,
      { latitude: 51.128, longitude: 71.431 },
      expect.any(Object),
    );
    expect(onSessionChanged).toHaveBeenCalledOnce();
  });

  it('keeps geolocation denial separate from backend errors', async () => {
    const startSession = vi.fn();
    const user = userEvent.setup();
    render(
      <Harness
        api={createApiStub({
          getActiveSession: vi.fn().mockRejectedValue(noActiveSession()),
          startSession,
        })}
        requestLocation={vi
          .fn()
          .mockRejectedValue(new GeolocationFailure('permission_denied'))}
      />,
    );
    await screen.findByText('Нет активной сессии');
    await user.click(screen.getByRole('button', { name: 'Начать сессию' }));

    expect(
      await screen.findByText(
        'Доступ к геопозиции запрещён. Разрешите его в настройках браузера.',
      ),
    ).toBeInTheDocument();
    expect(startSession).not.toHaveBeenCalled();
  });

  it('completes the active session without a reload', async () => {
    const completed = {
      ...activeSession,
      status: 'completed' as const,
      ended_at: '2026-08-04T06:30:00Z',
    };
    const completeActiveSession = vi.fn().mockResolvedValue(completed);
    const user = userEvent.setup();
    render(
      <Harness
        api={createApiStub({
          getActiveSession: vi.fn().mockResolvedValue(activeSession),
          completeActiveSession,
        })}
      />,
    );
    await screen.findByText('Сессия №7 активна');
    await user.click(screen.getByRole('button', { name: 'Завершить' }));

    expect(await screen.findByText('Нет активной сессии')).toBeInTheDocument();
    expect(completeActiveSession).toHaveBeenCalledWith(
      42,
      {},
      expect.any(Object),
    );
  });

  it('requires explicit confirmation before cancelling', async () => {
    const cancelled = {
      ...activeSession,
      status: 'cancelled' as const,
      ended_at: '2026-08-04T06:10:00Z',
    };
    const cancelActiveSession = vi.fn().mockResolvedValue(cancelled);
    const user = userEvent.setup();
    render(
      <Harness
        api={createApiStub({
          getActiveSession: vi.fn().mockResolvedValue(activeSession),
          cancelActiveSession,
        })}
      />,
    );
    await screen.findByText('Сессия №7 активна');
    await user.click(screen.getByRole('button', { name: 'Отменить' }));

    expect(screen.getByRole('alertdialog')).toBeInTheDocument();
    expect(cancelActiveSession).not.toHaveBeenCalled();
    await user.click(screen.getByRole('button', { name: 'Подтвердить отмену' }));

    expect(await screen.findByText('Нет активной сессии')).toBeInTheDocument();
    expect(cancelActiveSession).toHaveBeenCalledOnce();
  });

  it('keeps cancellation confirmation keyboard-safe', async () => {
    const user = userEvent.setup();
    render(
      <Harness
        api={createApiStub({
          getActiveSession: vi.fn().mockResolvedValue(activeSession),
        })}
      />,
    );
    await screen.findByText('Сессия №7 активна');
    const cancelButton = screen.getByRole('button', { name: 'Отменить' });
    await user.click(cancelButton);

    const returnButton = screen.getByRole('button', { name: 'Вернуться' });
    const confirmButton = screen.getByRole('button', {
      name: 'Подтвердить отмену',
    });
    expect(returnButton).toHaveFocus();
    await user.tab();
    expect(confirmButton).toHaveFocus();
    await user.tab({ shift: true });
    expect(returnButton).toHaveFocus();
    await user.keyboard('{Escape}');

    expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument();
    expect(cancelButton).toHaveFocus();
  });

  it('disables session start for an inactive device', async () => {
    render(
      <Harness
        api={createApiStub({
          getActiveSession: vi.fn().mockRejectedValue(noActiveSession()),
        })}
        deviceActive={false}
      />,
    );

    expect(
      await screen.findByRole('button', { name: 'Начать сессию' }),
    ).toBeDisabled();
    expect(screen.getByText('Сначала активируйте устройство.')).toBeInTheDocument();
  });
});
