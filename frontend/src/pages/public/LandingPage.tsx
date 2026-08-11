import { Link } from 'react-router';

import { AiriMascot } from '../../components/brand/AiriMascot';

const measurementSteps = [
  ['01', 'Подключите датчик', 'Выберите существующий ID или зарегистрируйте новое устройство.'],
  ['02', 'Выберите место', 'Установите датчик в точке исследования и оставьте воздухозаборник открытым.'],
  ['03', 'Начните сессию', 'Браузер один раз фиксирует координаты, а датчик собирает серию измерений на месте.'],
  ['04', 'Изучите результат', 'Сравните показания на графике, в таблице и среди других точек на карте.'],
] as const;

const metrics = [
  ['PM1.0', 'мкг/м³', 'Самые мелкие частицы'],
  ['PM2.5', 'мкг/м³', 'Мелкодисперсная пыль'],
  ['PM10', 'мкг/м³', 'Взвешенные частицы'],
  ['Температура', '°C', 'Условия в точке'],
  ['Влажность', '%', 'Контекст наблюдения'],
] as const;

export default function LandingPage() {
  return (
    <>
      <section className="hero public-container">
        <div className="hero__copy">
          <p className="eyebrow">Алматы · городская полевая лаборатория</p>
          <h1>Измеряем воздух Алматы — точка за точкой</h1>
          <p className="hero__lead">
            AirMonitor помогает установить переносной датчик в выбранном месте,
            провести серию измерений и сохранить результат на карте — без фонового
            отслеживания и перезагрузки страницы.
          </p>
          <div className="hero__actions">
            <Link className="button button--signal button--large" to="/app/measurement">
              Начать измерение
            </Link>
            <a className="button button--hero-quiet button--large" href="#how-it-works">
              Как это работает
            </a>
          </div>
          <dl className="hero__facts" aria-label="Ключевые особенности">
            <div><dt>5</dt><dd>показателей воздуха</dd></div>
            <div><dt>1 точка</dt><dd>на одну сессию</dd></div>
            <div><dt>5 сек</dt><dd>интервал обновления</dd></div>
          </dl>
        </div>

        <div className="hero__visual">
          <div className="hero__grid" aria-hidden="true" />
          <div className="hero__image-shell">
            <AiriMascot label="Айри — полевой робот-помощник AirMonitor" priority />
          </div>
          <div className="hero__identity">
            <span>Полевой помощник</span>
            <strong>Айри / AM–01</strong>
          </div>
          <div className="hero__point-card">
            <span className="hero__point-status"><i /> Точка готова</span>
            <strong>Алматы · 43.23° N</strong>
            <small>Координаты фиксируются один раз при начале сессии.</small>
          </div>
        </div>
      </section>

      <div className="signal-strip" aria-label="Возможности AirMonitor">
        <div className="public-container">
          <span>Полевые измерения</span><i />
          <span>Живая телеметрия</span><i />
          <span>Точки на карте</span><i />
          <span>История сессий</span>
        </div>
      </div>

      <section
        id="how-it-works"
        className="public-section public-container field-process-section"
        aria-labelledby="process-heading"
      >
        <div className="section-intro">
          <p className="eyebrow">Как проходит измерение</p>
          <h2 id="process-heading">От выбранного места до понятного результата</h2>
          <p>
            Четыре коротких шага в одном приложении. Исходные значения остаются
            доступны для точной проверки и сравнения.
          </p>
        </div>
        <ol className="field-process">
          {measurementSteps.map(([number, title, description]) => (
            <li key={number}>
              <span>{number}</span>
              <div><strong>{title}</strong><p>{description}</p></div>
            </li>
          ))}
        </ol>
      </section>

      <section className="public-section lab-story" aria-labelledby="what-heading">
        <div className="public-container lab-story__grid">
          <div className="lab-story__copy">
            <p className="eyebrow eyebrow--signal">Одна сессия — одна географическая точка</p>
            <h2 id="what-heading">Одна точка. Серия честных измерений.</h2>
            <p>
              AirMonitor связывает частицы, температуру, влажность и время с одним
              местом исследования. На карте каждая проведённая сессия становится
              отдельной изученной точкой города.
            </p>
            <Link className="text-link text-link--signal text-link--arrow" to="/methodology">
              Как читать измерения
            </Link>
          </div>
          <div className="lab-console" aria-label="Возможности рабочего пространства">
            <div className="lab-console__top"><span><i /> AIRMONITOR / POINT LOG</span><span>ALM</span></div>
            <div className="lab-console__points" aria-hidden="true"><i /><i /><i /><i /><i /></div>
            <div className="lab-console__cards">
              <article><span>Сессия</span><strong>Одна точка</strong><small>серия измерений на месте</small></article>
              <article><span>Карта</span><strong>Изученные места</strong><small>одна сессия — одна отметка</small></article>
              <article><span>История</span><strong>Точный архив</strong><small>курсорная пагинация</small></article>
            </div>
          </div>
        </div>
      </section>

      <section className="public-section public-container metric-section" aria-labelledby="metrics-heading">
        <div className="section-intro section-intro--row">
          <div><p className="eyebrow">Что видит датчик</p><h2 id="metrics-heading">Пять показателей — без ложных выводов</h2></div>
          <p>
            Серия значений показывает, как менялся воздух в выбранном месте во
            времени, но не является официальным AQI или медицинским заключением.
          </p>
        </div>
        <div className="metric-tape">
          {metrics.map(([name, unit, description], index) => (
            <article key={name} className={index === 1 ? 'metric-tape__featured' : undefined}>
              <span>{String(index + 1).padStart(2, '0')}</span>
              <strong>{name}</strong>
              <small>{description}</small>
              <em>{unit}</em>
            </article>
          ))}
        </div>
      </section>

      <section className="public-section public-container invitation" aria-labelledby="participation-heading">
        <div className="invitation__copy">
          <p className="eyebrow eyebrow--signal">Выберите точку исследования</p>
          <h2 id="participation-heading">Город становится понятнее, когда мы измеряем внимательно</h2>
          <p>
            Установите датчик в выбранном месте, соберите аккуратную сессию и
            сравните результат с другими исследованными точками Алматы.
          </p>
          <div className="button-row">
            <Link className="button button--signal" to="/app/measurement">Начать с Айри</Link>
            <Link className="button button--invitation-quiet" to="/participate">Как участвовать</Link>
          </div>
        </div>
        <div className="invitation__note">
          <span>Геопозиция точки</span>
          <strong>Только один запрос при старте</strong>
          <p>Никакого фонового отслеживания. Подложку OpenStreetMap можно отключить в локальных настройках.</p>
        </div>
      </section>

      <section className="public-section public-container faq-section" aria-labelledby="faq-heading">
        <div className="section-intro"><p className="eyebrow">Перед измерением</p><h2 id="faq-heading">Коротко о главном</h2></div>
        <div className="faq-list">
          <details><summary>Нужна ли учётная запись?</summary><p>Нет. Текущая версия работает с выбранным ID устройства.</p></details>
          <details><summary>Можно ли считать результат официальным показателем?</summary><p>Нет. Это наблюдение портативного датчика в конкретное время и в конкретном месте.</p></details>
          <details><summary>Что останется доступно без карты?</summary><p>Сессии, графики и точная таблица. Интернет нужен только для загрузки подложки OpenStreetMap.</p></details>
        </div>
      </section>
    </>
  );
}
