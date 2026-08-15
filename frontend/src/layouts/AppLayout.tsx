import { useState, type ReactNode } from 'react';
import { AppHeader } from '../components/navigation/AppHeader';
import { AppSidebar } from '../components/navigation/AppSidebar';
import { MobileNavigation } from '../components/navigation/MobileNavigation';

export function AppLayout({ children }: { readonly children: ReactNode }) {
  const [collapsed, setCollapsed] = useState(false);
  return <div className={`participant-shell${collapsed ? ' participant-shell--collapsed' : ''}`}><a className="skip-link" href="#app-main">К основному содержанию</a><AppSidebar collapsed={collapsed} onToggle={() => setCollapsed((value) => !value)} /><div className="participant-shell__content"><AppHeader /><main id="app-main" className="app-main" tabIndex={-1}>{children}</main></div><MobileNavigation /></div>;
}
