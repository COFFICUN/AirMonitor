import { useCallback, useEffect, useRef, useState } from 'react';

import { isApiError } from '../../api/errors';
import { apiErrorMessage } from '../../api/presentation';
import type {
  AirMonitorApi,
  DeviceCreateRequest,
  DeviceResponse,
} from '../../api/types';
import {
  clearSelectedDeviceId,
  readSelectedDeviceId,
  writeSelectedDeviceId,
} from '../../storage/deviceStorage';

export type DeviceSelectionStatus = 'idle' | 'loading' | 'ready' | 'error';

export interface DeviceSelection {
  readonly device: DeviceResponse | null;
  readonly status: DeviceSelectionStatus;
  readonly error: string | null;
  readonly persistenceAvailable: boolean;
  selectDeviceId(deviceId: number): Promise<boolean>;
  registerDevice(request: DeviceCreateRequest): Promise<boolean>;
  setActive(isActive: boolean): Promise<boolean>;
  clear(): void;
}

export function useSelectedDevice(api: AirMonitorApi): DeviceSelection {
  const [restoredDeviceId] = useState(readSelectedDeviceId);
  const [device, setDevice] = useState<DeviceResponse | null>(null);
  const [status, setStatus] = useState<DeviceSelectionStatus>(
    restoredDeviceId === null ? 'idle' : 'loading',
  );
  const [error, setError] = useState<string | null>(null);
  const [persistenceAvailable, setPersistenceAvailable] = useState(true);
  const requestRef = useRef<AbortController | null>(null);

  const beginRequest = useCallback((clearDevice: boolean) => {
    requestRef.current?.abort();
    const controller = new AbortController();
    requestRef.current = controller;
    if (clearDevice) {
      setDevice(null);
    }
    setError(null);
    setStatus('loading');
    return controller;
  }, []);

  const commitDevice = useCallback((selected: DeviceResponse) => {
    const stored = writeSelectedDeviceId(selected.id);
    setPersistenceAvailable(stored);
    setDevice(selected);
    setError(null);
    setStatus('ready');
  }, []);

  const finishRequest = useCallback((controller: AbortController) => {
    if (requestRef.current === controller) {
      requestRef.current = null;
    }
  }, []);

  const selectDeviceId = useCallback(
    async (deviceId: number): Promise<boolean> => {
      const controller = beginRequest(true);
      try {
        const selected = await api.getDevice(deviceId, {
          signal: controller.signal,
        });
        if (requestRef.current !== controller) {
          return false;
        }
        commitDevice(selected);
        return true;
      } catch (requestError) {
        if (
          requestRef.current !== controller ||
          (isApiError(requestError) && requestError.kind === 'aborted')
        ) {
          return false;
        }
        setStatus('error');
        setError(apiErrorMessage(requestError, 'Не удалось подключить устройство.'));
        return false;
      } finally {
        finishRequest(controller);
      }
    },
    [api, beginRequest, commitDevice, finishRequest],
  );

  const registerDevice = useCallback(
    async (request: DeviceCreateRequest): Promise<boolean> => {
      const controller = beginRequest(true);
      try {
        const selected = await api.createDevice(request, {
          signal: controller.signal,
        });
        if (requestRef.current !== controller) {
          return false;
        }
        commitDevice(selected);
        return true;
      } catch (requestError) {
        if (
          requestRef.current !== controller ||
          (isApiError(requestError) && requestError.kind === 'aborted')
        ) {
          return false;
        }
        setStatus('error');
        setError(
          apiErrorMessage(requestError, 'Не удалось зарегистрировать устройство.'),
        );
        return false;
      } finally {
        finishRequest(controller);
      }
    },
    [api, beginRequest, commitDevice, finishRequest],
  );

  const setActive = useCallback(
    async (isActive: boolean): Promise<boolean> => {
      if (device === null) {
        return false;
      }
      const controller = beginRequest(false);
      try {
        const updated = await api.setDeviceStatus(
          device.id,
          { is_active: isActive },
          { signal: controller.signal },
        );
        if (requestRef.current !== controller) {
          return false;
        }
        commitDevice(updated);
        return true;
      } catch (requestError) {
        if (
          requestRef.current !== controller ||
          (isApiError(requestError) && requestError.kind === 'aborted')
        ) {
          return false;
        }
        setStatus('error');
        setError(apiErrorMessage(requestError, 'Не удалось изменить состояние.'));
        return false;
      } finally {
        finishRequest(controller);
      }
    },
    [api, beginRequest, commitDevice, device, finishRequest],
  );

  const clear = useCallback(() => {
    requestRef.current?.abort();
    requestRef.current = null;
    setDevice(null);
    setStatus('idle');
    setError(null);
    setPersistenceAvailable(clearSelectedDeviceId());
  }, []);

  useEffect(() => {
    if (restoredDeviceId === null) {
      return;
    }
    const controller = beginRequest(true);
    void api
      .getDevice(restoredDeviceId, { signal: controller.signal })
      .then((selected) => {
        if (requestRef.current === controller) {
          commitDevice(selected);
        }
      })
      .catch((requestError: unknown) => {
        if (
          requestRef.current !== controller ||
          (isApiError(requestError) && requestError.kind === 'aborted')
        ) {
          return;
        }
        if (isApiError(requestError) && requestError.code === 'device_not_found') {
          setPersistenceAvailable(clearSelectedDeviceId());
          setStatus('error');
          setError('Сохранённое устройство не найдено. Выберите другое.');
          return;
        }
        setStatus('error');
        setError(
          apiErrorMessage(requestError, 'Не удалось восстановить устройство.'),
        );
      })
      .finally(() => finishRequest(controller));

    return () => {
      if (requestRef.current === controller) {
        controller.abort();
        requestRef.current = null;
      }
    };
  }, [api, beginRequest, commitDevice, finishRequest, restoredDeviceId]);

  useEffect(
    () => () => {
      requestRef.current?.abort();
      requestRef.current = null;
    },
    [],
  );

  return {
    device,
    status,
    error,
    persistenceAvailable,
    selectDeviceId,
    registerDevice,
    setActive,
    clear,
  };
}
