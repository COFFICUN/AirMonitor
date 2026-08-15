import { Outlet } from 'react-router';

import type { AirMonitorApi } from '../api/types';
import { AppLayout } from '../layouts/AppLayout';
import { AppDataProvider } from './AppDataContext';

export default function ParticipantApp({ api }: { readonly api: AirMonitorApi }) {
  return (
    <AppDataProvider api={api}>
      <AppLayout><Outlet /></AppLayout>
    </AppDataProvider>
  );
}
