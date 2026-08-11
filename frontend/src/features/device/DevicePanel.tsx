import { useState, type FormEvent } from 'react';

import type { DeviceSelection } from './useSelectedDevice';

interface DevicePanelProps {
  readonly selection: DeviceSelection;
}

function parseDeviceId(value: string): number | null {
  if (!/^[1-9]\d*$/.test(value)) {
    return null;
  }
  const deviceId = Number(value);
  return Number.isInteger(deviceId) && deviceId <= 2_147_483_647
    ? deviceId
    : null;
}

export function DevicePanel({ selection }: DevicePanelProps) {
  const [deviceIdInput, setDeviceIdInput] = useState('');
  const [deviceUid, setDeviceUid] = useState('');
  const [deviceName, setDeviceName] = useState('');
  const [formError, setFormError] = useState<string | null>(null);
  const busy = selection.status === 'loading';

  async function handleExistingSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const deviceId = parseDeviceId(deviceIdInput.trim());
    if (deviceId === null) {
      setFormError('Введите целый ID от 1 до 2147483647.');
      return;
    }
    setFormError(null);
    const selected = await selection.selectDeviceId(deviceId);
    if (selected) {
      setDeviceIdInput('');
    }
  }

  async function handleRegistrationSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const normalizedUid = deviceUid.trim();
    const normalizedName = deviceName.trim();
    if (normalizedUid === '') {
      setFormError('Введите UID нового устройства.');
      return;
    }
    setFormError(null);
    const registered = await selection.registerDevice({
      device_uid: normalizedUid,
      name: normalizedName === '' ? null : normalizedName,
      is_active: true,
    });
    if (registered) {
      setDeviceUid('');
      setDeviceName('');
    }
  }

  return (
    <section className="panel panel--device" aria-labelledby="device-heading">
      <div className="panel__heading-row">
        <div>
          <p className="panel__eyebrow">Локальный выбор</p>
          <h2 id="device-heading">Выбранный датчик</h2>
        </div>
        {selection.device !== null && (
          <span className="device-id">ID {selection.device.id}</span>
        )}
      </div>

      {selection.device !== null ? (
        <div className="device-summary" aria-busy={busy}>
          <p className="device-summary__state">Устройство подключено</p>
          <strong>{selection.device.device_uid}</strong>
          <span>{selection.device.name ?? 'Без названия'}</span>
          <span>
            Состояние: {selection.device.is_active ? 'Активно' : 'Неактивно'}
          </span>
          <div className="button-row">
            <button
              className="button button--quiet"
              type="button"
              disabled={busy}
              onClick={() => {
                void selection.setActive(!selection.device?.is_active);
              }}
            >
              {selection.device.is_active ? 'Деактивировать' : 'Активировать'}
            </button>
            <button
              className="button button--text"
              type="button"
              disabled={busy}
              onClick={selection.clear}
            >
              Очистить выбор
            </button>
          </div>
        </div>
      ) : (
        <p className="empty-copy">Выберите существующее устройство или создайте новое.</p>
      )}

      {(formError ?? selection.error) !== null && (
        <p className="form-message form-message--error" role="alert">
          {formError ?? selection.error}
        </p>
      )}
      {!selection.persistenceAvailable && (
        <p className="form-message" role="status">
          Браузер не разрешил сохранить выбор. Он действует до закрытия вкладки.
        </p>
      )}

      <div className="device-forms" aria-busy={busy}>
        <form onSubmit={(event) => void handleExistingSubmit(event)}>
          <label htmlFor="existing-device-id">ID существующего устройства</label>
          <div className="field-action">
            <input
              id="existing-device-id"
              type="number"
              min="1"
              max="2147483647"
              step="1"
              inputMode="numeric"
              value={deviceIdInput}
              disabled={busy}
              onChange={(event) => setDeviceIdInput(event.target.value)}
            />
            <button className="button" type="submit" disabled={busy}>
              Подключить
            </button>
          </div>
        </form>

        <form onSubmit={(event) => void handleRegistrationSubmit(event)}>
          <label htmlFor="new-device-uid">UID нового устройства</label>
          <input
            id="new-device-uid"
            type="text"
            maxLength={255}
            value={deviceUid}
            disabled={busy}
            onChange={(event) => setDeviceUid(event.target.value)}
          />
          <label htmlFor="new-device-name">Название устройства</label>
          <input
            id="new-device-name"
            type="text"
            maxLength={255}
            value={deviceName}
            disabled={busy}
            onChange={(event) => setDeviceName(event.target.value)}
          />
          <button className="button button--quiet" type="submit" disabled={busy}>
            Зарегистрировать
          </button>
        </form>
      </div>
    </section>
  );
}
