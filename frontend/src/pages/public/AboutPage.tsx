import { Link } from 'react-router';

import { AiriMascot } from '../../components/brand/AiriMascot';

export default function AboutPage() {
  return (
    <article className="public-page public-container">
      <header className="public-page__hero">
        <div>
          <p className="eyebrow">О проекте</p>
          <h1>О проекте AirMonitor</h1>
          <p>
            Инженерный и учебно-исследовательский инструмент для аккуратного
            сбора наблюдений за воздухом в отдельных точках Алматы.
          </p>
        </div>
        <AiriMascot compact />
      </header>
      <section className="content-grid">
        <div><h2>Зачем он нужен</h2><p>Проект помогает сравнивать воздух в исследованных местах и задавать более точные вопросы к данным.</p></div>
        <div><h2>Как устроена система</h2><p>Портативный датчик отправляет серию измерений. Сессия связывает их с одним временем старта и одной географической точкой.</p></div>
        <div><h2>Что уже работает</h2><p>Устройства, сессии, живые обновления, история, графики, таблица и карта измерительных точек.</p></div>
        <div><h2>Текущие ограничения</h2><p>Это не государственная сеть мониторинга, не медицинский сервис и не система личных аккаунтов.</p></div>
      </section>
      <aside className="notice-card">
        <strong>Принцип данных</strong>
        <p>Одна измерительная сессия соответствует одной географической точке. Новое место — новая сессия.</p>
      </aside>
      <Link className="button button--primary" to="/app">Перейти к приложению</Link>
    </article>
  );
}
