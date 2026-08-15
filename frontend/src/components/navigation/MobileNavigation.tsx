import { NavLink } from 'react-router';
import { Icon } from '../ui/Icon';
import { APP_NAVIGATION } from '../../layouts/appNavigation';

const visible = APP_NAVIGATION.slice(0, 5);
export function MobileNavigation() { return <nav className="mobile-navigation" aria-label="Мобильная навигация">{visible.map((item) => <NavLink key={item.to} to={item.to} end={item.end}><Icon name={item.icon} size={19} /><span>{item.shortLabel}</span></NavLink>)}</nav>; }
