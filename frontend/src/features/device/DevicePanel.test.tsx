import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { ApiError } from '../../api/errors';
import type { AirMonitorApi, DeviceResponse } from '../../api/types';
import {
  DEVICE_STORAGE_KEY,
  writeSelectedDeviceId,
} from '../../storage/deviceStorage';
import { createApiStub } from '../../test/apiStub';
import { DevicePanel } from './DevicePanel';
import { useSelectedDevice } from './useSelectedDevice';

const activeDevice: DeviceResponse = {
  id: 42,
  device_uid: 'sensor-42',
  name: 'Лаборатория',
  is_active: true,
  created_at: '2026-08-04T06:00:00Z',
};

function Harness({ api }: { readonly api: AirMonitorApi }) {
  const selection = useSelectedDevice(api);
  return <DevicePanel selection={selection} />;
}

beforeEach(() => {
  localStorage.clear();
});

describe('DevicePanel', () => {
  it('verifies and persists an entered existing device ID', async () => {
    const getDevice = vi.fn().mockResolvedValue(activeDevice);
    const api = createApiStub({ getDevice });
    const user = userEvent.setup();

    render(<Harness api={api} />);
    await user.type(
      screen.getByRole('spinbutton', { name: 'ID существующего устройства' }),
      '42',
    );
    await user.click(screen.getByRole('button', { name: 'Подключить' }));

    expect(await screen.findByText('sensor-42')).toBeInTheDocument();
    expect(getDevice).toHaveBeenCalledWith(42, expect.any(Object));
    expect(localStorage.getItem(DEVICE_STORAGE_KEY)).toBe(
      JSON.stringify({ version: 1, deviceId: 42 }),
    );
  });

  it('registers a new active device and selects the returned ID', async () => {
    const createDevice = vi.fn().mockResolvedValue(activeDevice);
    const api = createApiStub({ createDevice });
    const user = userEvent.setup();

    render(<Harness api={api} />);
    await user.type(screen.getByRole('textbox', { name: 'UID нового устройства' }), 'sensor-42');
    await user.type(screen.getByRole('textbox', { name: 'Название устройства' }), 'Лаборатория');
    await user.click(screen.getByRole('button', { name: 'Зарегистрировать' }));

    expect(await screen.findByText('Устройство подключено')).toBeInTheDocument();
    expect(createDevice).toHaveBeenCalledWith(
      {
        device_uid: 'sensor-42',
        name: 'Лаборатория',
        is_active: true,
      },
      expect.any(Object),
    );
    expect(localStorage.getItem(DEVICE_STORAGE_KEY)).toContain('42');
  });

  it('restores and verifies a saved device on mount', async () => {
    writeSelectedDeviceId(42);
    const getDevice = vi.fn().mockResolvedValue(activeDevice);

    render(<Harness api={createApiStub({ getDevice })} />);

    expect(await screen.findByText('sensor-42')).toBeInTheDocument();
    expect(getDevice).toHaveBeenCalledWith(42, expect.any(Object));
  });

  it('removes a saved ID when the backend confirms the device is absent', async () => {
    writeSelectedDeviceId(42);
    const api = createApiStub({
      getDevice: vi.fn().mockRejectedValue(
        new ApiError({
          kind: 'http',
          status: 404,
          code: 'device_not_found',
          publicMessage: 'Device was not found.',
        }),
      ),
    });

    render(<Harness api={api} />);

    expect(
      await screen.findByText('Сохранённое устройство не найдено. Выберите другое.'),
    ).toBeInTheDocument();
    expect(localStorage.getItem(DEVICE_STORAGE_KEY)).toBeNull();
  });

  it('updates device status and exposes a clear action', async () => {
    const inactiveDevice = { ...activeDevice, is_active: false };
    const setDeviceStatus = vi.fn().mockResolvedValue(inactiveDevice);
    const api = createApiStub({
      getDevice: vi.fn().mockResolvedValue(activeDevice),
      setDeviceStatus,
    });
    const user = userEvent.setup();
    writeSelectedDeviceId(42);

    render(<Harness api={api} />);
    await screen.findByText('sensor-42');
    await user.click(screen.getByRole('button', { name: 'Деактивировать' }));

    expect(
      await screen.findByText('Состояние: Неактивно'),
    ).toBeInTheDocument();
    expect(setDeviceStatus).toHaveBeenCalledWith(
      42,
      { is_active: false },
      expect.any(Object),
    );

    await user.click(screen.getByRole('button', { name: 'Очистить выбор' }));
    expect(screen.queryByText('sensor-42')).not.toBeInTheDocument();
    expect(localStorage.getItem(DEVICE_STORAGE_KEY)).toBeNull();
  });
});
