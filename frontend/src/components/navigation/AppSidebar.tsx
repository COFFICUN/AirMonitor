import { NavLink } from 'react-router';
import { Brand } from '../brand/Brand';
import { Icon } from '../ui/Icon';
import { APP_NAVIGATION } from '../../layouts/appNavigation';

export function AppSidebar({ collapsed, onToggle }: { readonly collapsed: boolean; readonly onToggle: () => void }) {
  return <aside className={`app-sidebar${collapsed ? ' app-sidebar--collapsed' : ''}`}><div className="app-sidebar__brand"><Brand to="/" /><button className="sidebar-toggle" type="button" aria-label={collapsed ? 'Развернуть меню' : 'Свернуть меню'} onClick={onToggle}>‹</button></div><nav aria-label="Разделы приложения">{APP_NAVIGATION.map((item) => <NavLink key={item.to} to={item.to} end={item.end}><Icon name={item.icon} /><span>{item.label}</span></NavLink>)}</nav><div className="app-sidebar__footer"><span className="participant-avatar" aria-hidden="true">У</span><span><strong>Участник</strong><small>Локальный режим</small></span></div></aside>;
}
