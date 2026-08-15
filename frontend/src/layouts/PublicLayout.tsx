import { useEffect, useState } from 'react';
import { NavLink, Outlet } from 'react-router';
import { Brand } from '../components/brand/Brand';
import { Icon } from '../components/ui/Icon';

const links = [
  { to: '/about', label: 'О проекте' },
  { to: '/participate', label: 'Участвовать' },
  { to: '/methodology', label: 'Методика' },
] as const;

export function PublicLayout() {
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    if (!menuOpen) return;
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setMenuOpen(false);
    };
    document.addEventListener('keydown', closeOnEscape);
    return () => document.removeEventListener('keydown', closeOnEscape);
  }, [menuOpen]);

  return (
    <div className="public-shell">
      <a className="skip-link" href="#main-content">К основному содержанию</a>
      <header className="public-header">
        <div className="public-container public-header__inner">
          <Brand />
          <nav className="public-nav" aria-label="Основная навигация">
            {links.map((link) => <NavLink key={link.to} to={link.to}>{link.label}</NavLink>)}
          </nav>
          <div className="public-header__actions">
            <NavLink className="text-link" to="/login">Войти</NavLink>
            <NavLink className="button button--primary button--small" to="/app">Открыть приложение</NavLink>
            <button className="public-menu-button" type="button" aria-expanded={menuOpen} aria-controls="public-mobile-menu" aria-label={menuOpen ? 'Закрыть меню' : 'Открыть меню'} onClick={() => setMenuOpen((value) => !value)}><Icon name={menuOpen ? 'close' : 'menu'} /></button>
          </div>
        </div>
        <nav id="public-mobile-menu" className={`public-mobile-menu${menuOpen ? ' public-mobile-menu--open' : ''}`} aria-label="Мобильная навигация">
          {links.map((link) => <NavLink key={link.to} to={link.to} onClick={() => setMenuOpen(false)}>{link.label}</NavLink>)}
          <NavLink to="/login" onClick={() => setMenuOpen(false)}>Войти</NavLink>
        </nav>
      </header>
      <main id="main-content" tabIndex={-1}><Outlet /></main>
      <footer className="public-footer">
        <div className="public-container public-footer__grid">
          <div><Brand /><p>Учебно-исследовательский инструмент для наблюдений за воздухом Алматы.</p></div>
          <nav aria-label="Ссылки в подвале"><NavLink to="/about">О проекте</NavLink><NavLink to="/methodology">Как читать данные</NavLink><NavLink to="/app">Приложение</NavLink></nav>
          <p className="public-footer__note">Данные датчика не заменяют официальные измерения или рекомендации специалистов.</p>
        </div>
      </footer>
    </div>
  );
}
