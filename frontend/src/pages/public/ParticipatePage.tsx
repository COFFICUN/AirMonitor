import { Link } from 'react-router';

export default function ParticipatePage() {
  return (
    <article className="public-page public-container">
      <header className="public-page__intro">
        <p className="eyebrow">Полевое измерение</p>
        <h1>Как участвовать</h1>
        <p>
          Нужен совместимый датчик AirMonitor и его ID. Регистрация участника или
          официальная заявка не требуется.
        </p>
      </header>
      <ol className="participation-steps">
        <li><span>1</span><div><h2>Подключите датчик</h2><p>Выберите существующий ID или зарегистрируйте устройство.</p></div></li>
        <li><span>2</span><div><h2>Выберите место</h2><p>Разместите сенсор устойчиво и убедитесь, что поток воздуха не перекрыт.</p></div></li>
        <li><span>3</span><div><h2>Начните сессию</h2><p>Разрешите разовое определение позиции и оставьте датчик собирать показания на месте.</p></div></li>
        <li><span>4</span><div><h2>Завершите и проверьте</h2><p>Откройте точку на карте, изучите график и точные значения в таблице.</p></div></li>
        <li><span>5</span><div><h2>Сравнивайте ответственно</h2><p>AirMonitor не превращает наблюдение в официальный индекс и не отправляет его в исследование от вашего имени.</p></div></li>
      </ol>
      <div className="action-band">
        <div><h2>Готовы измерить новую точку?</h2><p>Проверьте датчик и начните отдельную сессию для выбранного места.</p></div>
        <Link className="button button--primary" to="/app/measurement">Начать измерение</Link>
      </div>
    </article>
  );
}
