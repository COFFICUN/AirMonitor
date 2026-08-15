export default function MethodologyPage() {
  return (
    <article className="public-page public-container methodology-page">
      <header className="public-page__intro">
        <p className="eyebrow">Методика</p>
        <h1>Как читать измерения</h1>
        <p>Каждая запись описывает условия у датчика в конкретный момент внутри одной сессии.</p>
      </header>
      <section>
        <h2>Взвешенные частицы</h2>
        <div className="definition-grid">
          <article><strong>PM1.0</strong><p>Частицы с аэродинамическим диаметром примерно до 1 мкм.</p></article>
          <article><strong>PM2.5</strong><p>Мелкодисперсная фракция примерно до 2,5 мкм.</p></article>
          <article><strong>PM10</strong><p>Фракция частиц примерно до 10 мкм.</p></article>
        </div>
      </section>
      <section className="methodology-split">
        <div><h2>Температура и влажность</h2><p>Дают контекст измерению, но не являются прогнозом погоды.</p></div>
        <div><h2>Время и позиция</h2><p>Все записи сессии относятся к одной географической точке, зафиксированной при старте. Время показывает изменение условий на месте.</p></div>
      </section>
      <section>
        <h2>Как проводить сессию</h2>
        <ul className="check-list">
          <li>Установите датчик устойчиво в выбранной точке.</li>
          <li>Держите воздухозаборник открытым.</li>
          <li>Избегайте намеренного контакта с дымом и аэрозолями.</li>
          <li>Для другого места завершите текущую сессию и начните новую.</li>
        </ul>
      </section>
      <aside className="notice-card notice-card--warning">
        <strong>Важно об ориентирах</strong>
        <p>Рекомендации ВОЗ задаются для периодов усреднения. Мгновенное значение AirMonitor не равно 24-часовому среднему, не является AQI и не даёт медицинского заключения.</p>
      </aside>
    </article>
  );
}
