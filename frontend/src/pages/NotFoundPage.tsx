import { Link } from 'react-router';

export default function NotFoundPage() {
  return <main id="main-content" className="not-found public-container" tabIndex={-1}><p className="eyebrow">Ошибка 404</p><h1>Страница не найдена</h1><p>Возможно, адрес изменился или в нём есть опечатка.</p><div className="button-row"><Link className="button button--primary" to="/">На главную</Link><Link className="button button--secondary" to="/app">В приложение</Link></div></main>;
}
