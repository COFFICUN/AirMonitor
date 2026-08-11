import { lazy, Suspense } from 'react';
import { Route, Routes } from 'react-router';

import { apiClient } from './api/client';
import type { AirMonitorApi } from './api/types';
import { PreferencesProvider } from './app/PreferencesContext';
import { PublicLayout } from './layouts/PublicLayout';

const LandingPage = lazy(() => import('./pages/public/LandingPage'));
const AboutPage = lazy(() => import('./pages/public/AboutPage'));
const ParticipatePage = lazy(() => import('./pages/public/ParticipatePage'));
const MethodologyPage = lazy(() => import('./pages/public/MethodologyPage'));
const LoginPage = lazy(() => import('./pages/public/LoginPage'));
const NotFoundPage = lazy(() => import('./pages/NotFoundPage'));
const ParticipantApp = lazy(() => import('./app/ParticipantApp'));
const OverviewPage = lazy(() => import('./pages/app/OverviewPage'));
const MeasurementPage = lazy(() => import('./pages/app/MeasurementPage'));
const SessionsPage = lazy(() => import('./pages/app/SessionsPage'));
const MapPage = lazy(() => import('./pages/app/MapPage'));
const DataPage = lazy(() => import('./pages/app/DataPage'));
const DevicePage = lazy(() => import('./pages/app/DevicePage'));
const SettingsPage = lazy(() => import('./pages/app/SettingsPage'));

function RouteFallback() {
  return <div className="route-loading" role="status">Загружаем страницу…</div>;
}

export function App({ api = apiClient }: { readonly api?: AirMonitorApi }) {
  return (
    <PreferencesProvider>
      <Suspense fallback={<RouteFallback />}>
        <Routes>
          <Route element={<PublicLayout />}>
            <Route index element={<LandingPage />} />
            <Route path="about" element={<AboutPage />} />
            <Route path="participate" element={<ParticipatePage />} />
            <Route path="methodology" element={<MethodologyPage />} />
            <Route path="login" element={<LoginPage />} />
          </Route>
          <Route path="app" element={<ParticipantApp api={api} />}>
            <Route index element={<OverviewPage />} />
            <Route path="measurement" element={<MeasurementPage />} />
            <Route path="sessions" element={<SessionsPage />} />
            <Route path="map" element={<MapPage />} />
            <Route path="data" element={<DataPage />} />
            <Route path="device" element={<DevicePage />} />
            <Route path="settings" element={<SettingsPage />} />
          </Route>
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </Suspense>
    </PreferencesProvider>
  );
}
