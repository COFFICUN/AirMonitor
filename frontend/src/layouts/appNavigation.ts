import type { IconName } from '../components/ui/Icon';

export interface AppNavigationItem { readonly to: string; readonly label: string; readonly shortLabel: string; readonly icon: IconName; readonly end?: boolean; }
export const APP_NAVIGATION: readonly AppNavigationItem[] = [
  { to: '/app', label: 'Обзор', shortLabel: 'Обзор', icon: 'overview', end: true },
  { to: '/app/measurement', label: 'Новое измерение', shortLabel: 'Измерение', icon: 'measurement' },
  { to: '/app/sessions', label: 'Мои сессии', shortLabel: 'Сессии', icon: 'sessions' },
  { to: '/app/map', label: 'Карта', shortLabel: 'Карта', icon: 'map' },
  { to: '/app/data', label: 'Данные', shortLabel: 'Данные', icon: 'data' },
  { to: '/app/device', label: 'Моё устройство', shortLabel: 'Устройство', icon: 'device' },
  { to: '/app/settings', label: 'Настройки', shortLabel: 'Настройки', icon: 'settings' },
];
