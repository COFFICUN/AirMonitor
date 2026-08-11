import { useAppData } from '../../app/AppDataContext';
import { Card } from '../../components/ui/Card';
import { PageHeader } from '../../components/ui/Headings';
import { DevicePanel } from '../../features/device/DevicePanel';

export default function DevicePage() { const { selection } = useAppData(); return <div className="app-page"><PageHeader eyebrow="Локальный выбор" title="Моё устройство" description="Подключите один датчик по ID или зарегистрируйте новый. Выбранный ID сохраняется только в этом браузере." /><div className="device-page-grid"><DevicePanel selection={selection} /><Card className="device-help"><h2>Что хранится локально</h2><p>Только числовой ID выбранного устройства и безобидные настройки интерфейса.</p><h2>Чего здесь нет</h2><p>Паролей, токенов, координат, истории измерений, данных Wi-Fi, батареи или прошивки.</p></Card></div></div>; }
