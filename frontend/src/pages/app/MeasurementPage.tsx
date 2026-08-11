import { Link } from 'react-router';

import { useAppData } from '../../app/AppDataContext';
import { Card } from '../../components/ui/Card';
import { PageHeader } from '../../components/ui/Headings';
import { StatusBadge } from '../../components/ui/Status';
import { SessionPanel } from '../../features/session/SessionPanel';
import { LiveTelemetryPanel } from '../../features/telemetry/LiveTelemetryPanel';

export default function MeasurementPage() {
  const { selection, activeSession, liveTelemetry } = useAppData();

  return (
    <div className="app-page measurement-page">
      <PageHeader
        eyebrow="Полевой режим"
        title="Новое измерение"
        description="Установите активный датчик в выбранной точке, начните сессию и наблюдайте за показаниями на месте."
      />
      {!selection.device && (
        <Card className="measurement-prerequisite">
          <div>
            <StatusBadge tone="warning">Нужно устройство</StatusBadge>
            <h2>Сначала подключите датчик</h2>
            <p>Введите известный ID или зарегистрируйте новый датчик. После этого вернитесь к измерению.</p>
          </div>
          <Link className="button button--primary" to="/app/device">Подключить устройство</Link>
        </Card>
      )}
      <div className="measurement-layout">
        <SessionPanel session={activeSession} deviceActive={selection.device?.is_active ?? false} />
        <LiveTelemetryPanel telemetry={liveTelemetry} />
      </div>
      <Card className="instruction-card">
        <div>
          <p className="panel__eyebrow">Одна сессия — одна точка</p>
          <h2>Во время измерения</h2>
        </div>
        <ol>
          <li>Установите датчик устойчиво и оставьте воздухозаборник открытым.</li>
          <li>Не держите датчик вплотную к одежде и не переносите его во время сессии.</li>
          <li>Не обновляйте страницу — значения приходят автоматически.</li>
          <li>Завершите сессию перед переходом в другое место.</li>
        </ol>
        <p>Геопозиция запрашивается один раз при старте. Постоянное отслеживание не используется.</p>
      </Card>
    </div>
  );
}
