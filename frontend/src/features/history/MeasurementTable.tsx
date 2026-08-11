import type { MeasurementResponse } from '../../api/types';
import { formatDateTime } from '../../utils/dateTime';

interface MeasurementTableProps {
  readonly measurements: readonly MeasurementResponse[];
}

function exactValue(value: number | null): string {
  return value === null ? '—' : String(value).replace('.', ',');
}

export function MeasurementTable({ measurements }: MeasurementTableProps) {
  return (
    <div className="table-scroll" tabIndex={0} aria-label="Таблица измерений">
      <table className="measurement-table">
        <caption>Точные значения, новые измерения показаны первыми</caption>
        <thead>
          <tr>
            <th scope="col">ID</th>
            <th scope="col">Время</th>
            <th scope="col">PM1.0, мкг/м³</th>
            <th scope="col">PM2.5, мкг/м³</th>
            <th scope="col">PM10, мкг/м³</th>
            <th scope="col">Темп., °C</th>
            <th scope="col">Влажн., %</th>
            <th scope="col">Качество</th>
          </tr>
        </thead>
        <tbody>
          {measurements.map((measurement) => (
            <tr key={measurement.id}>
              <td>{measurement.id}</td>
              <td>
                <time dateTime={measurement.measured_at}>
                  {formatDateTime(measurement.measured_at)}
                </time>
              </td>
              <td>{exactValue(measurement.pm1)}</td>
              <td>{exactValue(measurement.pm25)}</td>
              <td>{exactValue(measurement.pm10)}</td>
              <td>{exactValue(measurement.temperature)}</td>
              <td>{exactValue(measurement.humidity)}</td>
              <td>{measurement.is_valid ? 'Валидно' : 'Отклонено'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

