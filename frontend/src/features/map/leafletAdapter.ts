import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

import type { SessionResponse } from '../../api/types';
import { formatDateTime } from '../../utils/dateTime';

export interface SessionMapController {
  update(
    sessions: readonly SessionResponse[],
    selectedSessionId: number | null,
    onSelect: (sessionId: number) => void,
  ): void;
  destroy(): void;
}

function popupContent(session: SessionResponse): HTMLElement {
  const root = document.createElement('div');
  const title = document.createElement('strong');
  title.textContent = `Сессия №${session.id}`;
  const details = document.createElement('p');
  const status = session.status === 'completed' ? 'Завершена' : session.status === 'active' ? 'Активна' : 'Отменена';
  details.textContent = `${formatDateTime(session.started_at)} · ${session.sample_count} измерений · ${status}`;
  root.append(title, details);
  return root;
}

export function createSessionMap(element: HTMLElement): SessionMapController {
  const map = L.map(element, {
    attributionControl: true,
    fadeAnimation: false,
    markerZoomAnimation: false,
    zoomAnimation: false,
    zoomControl: true,
  }).setView([43.2389, 76.8897], 11);
  L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution:
      '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    maxZoom: 19,
  }).addTo(map);
  const markerLayer = L.layerGroup().addTo(map);

  return {
    update(sessions, selectedSessionId, onSelect) {
      markerLayer.clearLayers();
      const markers = sessions.map((session) => {
        const selected = session.id === selectedSessionId;
        const fillColor = session.status === 'active' ? '#c8f169' : session.status === 'completed' ? '#1c8b72' : '#7b8d86';
        const marker = L.circleMarker([session.latitude, session.longitude], {
          radius: selected ? 10 : 7,
          color: selected ? '#0b2928' : '#ffffff',
          weight: selected ? 3 : 2,
          fillColor,
          fillOpacity: 0.96,
        })
          .bindTooltip(`Сессия №${session.id}`, { direction: 'top', offset: [0, -8] })
          .bindPopup(popupContent(session), { autoPan: false })
          .on('click', () => onSelect(session.id))
          .addTo(markerLayer);
        return { marker, session };
      });

      const selected = markers.find(
        ({ session }) => session.id === selectedSessionId,
      );
      if (selected !== undefined) {
        map.setView(
          [selected.session.latitude, selected.session.longitude],
          Math.max(map.getZoom(), 13),
          { animate: false },
        );
        selected.marker.openPopup();
      } else if (markers.length === 1) {
        const only = markers[0]!.session;
        map.setView([only.latitude, only.longitude], 13, { animate: false });
      } else if (markers.length > 1) {
        const bounds = L.latLngBounds(
          markers.map(({ session }) => [session.latitude, session.longitude]),
        );
        map.fitBounds(bounds, {
          animate: false,
          padding: [24, 24],
          maxZoom: 14,
        });
      }
      map.invalidateSize({ animate: false });
    },
    destroy() {
      markerLayer.clearLayers();
      map.remove();
    },
  };
}
