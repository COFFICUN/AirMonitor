import { Link } from 'react-router';
import { useAppData } from '../../app/AppDataContext';
import { StatusBadge } from '../ui/Status';

export function AppHeader() {
  const { health, selection } = useAppData();
  return <header className="app-header"><div><p className="app-header__context">AirMonitor · Алматы</p><Link className="app-header__device" to="/app/device">{selection.device === null ? 'Устройство не выбрано' : selection.device.name ?? selection.device.device_uid}</Link></div><div className="app-header__status"><StatusBadge tone={health.status === 'available' ? 'success' : health.status === 'loading' ? 'neutral' : 'danger'}>{health.status === 'available' ? 'Система доступна' : health.status === 'loading' ? 'Проверяем систему' : 'Нет связи'}</StatusBadge><Link className="participant-chip" to="/app/settings"><span aria-hidden="true">У</span>Участник</Link></div></header>;
}
