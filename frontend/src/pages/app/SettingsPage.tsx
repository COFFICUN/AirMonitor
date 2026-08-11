import { Link } from 'react-router';

import { useAppData } from '../../app/AppDataContext';
import { usePreferences } from '../../app/PreferencesContext';
import { Card } from '../../components/ui/Card';
import { Field, Select } from '../../components/ui/Forms';
import { PageHeader } from '../../components/ui/Headings';
import type {
  DisplayDensity,
  MotionPreference,
  PollingInterval,
  ThemePreference,
  TimeFormatPreference,
} from '../../storage/preferencesStorage';

export default function SettingsPage() {
  const { selection } = useAppData();
  const { preferences, persistenceAvailable, update, reset } = usePreferences();
  const device = selection.device;

  return (
    <div className="app-page">
      <PageHeader
        eyebrow="Только этот браузер"
        title="Настройки"
        description="Настройте вид и частоту обновления интерфейса. Эти параметры не отправляются на сервер."
      />

      <div className="settings-page-grid">
        <Card className="settings-card">
          <div className="settings-grid">
            <Field label="Тема интерфейса" hint="Системная тема следует настройке светлого или тёмного режима устройства.">
              <Select value={preferences.theme} onChange={(event) => update({ theme: event.target.value as ThemePreference })}>
                <option value="system">Как в системе</option>
                <option value="light">Светлая</option>
                <option value="dark">Тёмная</option>
              </Select>
            </Field>

            <Field label="Плотность интерфейса" hint="Компактный режим уменьшает вертикальные отступы.">
              <Select value={preferences.density} onChange={(event) => update({ density: event.target.value as DisplayDensity })}>
                <option value="comfortable">Комфортная</option>
                <option value="compact">Компактная</option>
              </Select>
            </Field>

            <Field label="Анимация интерфейса" hint="Системное значение всегда учитывает prefers-reduced-motion.">
              <Select value={preferences.motion} onChange={(event) => update({ motion: event.target.value as MotionPreference })}>
                <option value="system">Как в системе</option>
                <option value="full">Мягкая анимация</option>
                <option value="reduced">Без анимации</option>
              </Select>
            </Field>

            <Field label="Формат времени">
              <Select value={preferences.timeFormat} onChange={(event) => update({ timeFormat: event.target.value as TimeFormatPreference })}>
                <option value="24h">24 часа</option>
                <option value="12h">12 часов</option>
              </Select>
            </Field>

            <Field label="Обновление показаний">
              <Select value={preferences.pollingIntervalMs} onChange={(event) => update({ pollingIntervalMs: Number(event.target.value) as PollingInterval })}>
                <option value={5_000}>Каждые 5 секунд</option>
                <option value={10_000}>Каждые 10 секунд</option>
                <option value={30_000}>Каждые 30 секунд</option>
              </Select>
            </Field>

            <label className="toggle-field">
              <input
                type="checkbox"
                checked={preferences.mapTilesEnabled}
                onChange={(event) => update({ mapTilesEnabled: event.target.checked })}
              />
              <span>
                <strong>Загружать OpenStreetMap</strong>
                <small>Без подложки списки, графики и таблица продолжают работать.</small>
              </span>
            </label>
          </div>

          {!persistenceAvailable && (
            <p className="form-message form-message--warning" role="status">
              Браузер не разрешил сохранить настройки. Они действуют до закрытия вкладки.
            </p>
          )}

          <button className="button button--danger" type="button" onClick={reset}>
            Сбросить настройки отображения
          </button>
        </Card>

        <Card className="settings-device-card">
          <div>
            <small>Предпочитаемое устройство</small>
            <h2>{device?.name ?? device?.device_uid ?? 'Устройство не выбрано'}</h2>
          </div>

          {device === null ? (
            <p>Подключите датчик, чтобы он открывался автоматически в этом браузере.</p>
          ) : (
            <dl>
              <div><dt>UID</dt><dd>{device.device_uid}</dd></div>
              <div><dt>Локальный ID</dt><dd>{device.id}</dd></div>
              <div><dt>Состояние</dt><dd>{device.is_active ? 'Активно' : 'Неактивно'}</dd></div>
            </dl>
          )}

          <p>Сохраняется только числовой ID — без токенов, координат и истории измерений.</p>
          <Link className="button button--secondary" to="/app/device">
            {device === null ? 'Выбрать устройство' : 'Изменить устройство'}
          </Link>
        </Card>
      </div>
    </div>
  );
}
