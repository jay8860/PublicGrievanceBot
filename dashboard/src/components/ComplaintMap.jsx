// Leaflet map in two modes: classic pins (default) or a density heat view.
import React, { useEffect } from 'react';
import { MapContainer, Marker, Popup, TileLayer, useMap } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { heatCells, severityColor } from '../lib/mapData';

// A pin drawn as inline SVG, coloured by priority. Cached per severity so
// markers keep a stable icon object between renders.
const ICONS = new Map();

function pinIcon(severity) {
  const key = severity || 'Unknown';
  if (ICONS.has(key)) return ICONS.get(key);

  const html = `
    <svg xmlns="http://www.w3.org/2000/svg" width="24" height="34" viewBox="0 0 24 34">
      <path d="M12 1C6 1 1.5 5.6 1.5 11.3 1.5 19.4 12 33 12 33s10.5-13.6 10.5-21.7C22.5 5.6 18 1 12 1z"
            fill="${severityColor(key)}" stroke="#ffffff" stroke-width="1.5"/>
      <circle cx="12" cy="11.3" r="3.8" fill="#ffffff" fill-opacity="0.92"/>
    </svg>`;

  const icon = L.divIcon({
    html,
    className: 'grievance-pin',
    iconSize: [24, 34],
    iconAnchor: [12, 33],
    popupAnchor: [0, -30],
  });
  ICONS.set(key, icon);
  return icon;
}

function FitBounds({ points }) {
  const map = useMap();
  // Stable key: the parent re-creates the points array on every render.
  const signature = points.map((point) => `${point.lat},${point.lon}`).join('|');

  useEffect(() => {
    if (points.length === 1) map.setView([points[0].lat, points[0].lon], 14);
    else if (points.length > 1) {
      map.fitBounds(points.map((point) => [point.lat, point.lon]),
        { padding: [30, 30], maxZoom: 14 });
    }
  }, [signature, map]);
  return null;
}

function HeatLayer({ points }) {
  const map = useMap();
  const signature = points.map((point) => point.id).join('|');

  useEffect(() => {
    const group = L.layerGroup().addTo(map);

    heatCells(points).forEach((cell) => {
      L.circle([cell.lat, cell.lon], {
        radius: 420 + cell.count * 240, stroke: false, fillColor: cell.color, fillOpacity: 0.18,
      }).addTo(group);
      L.circle([cell.lat, cell.lon], {
        radius: 220 + cell.count * 130, stroke: false, fillColor: cell.color, fillOpacity: 0.3,
      }).addTo(group);
    });

    return () => { map.removeLayer(group); };
  }, [signature, map]);

  return null;
}

export default function ComplaintMap({ points = [], onSelect, height = 560, mode = 'pins' }) {
  const placed = points.filter((point) => point.lat != null && point.lon != null);
  const centre = placed.length ? [placed[0].lat, placed[0].lon] : [20.707, 81.55];

  return (
    <div style={{ height }} className="overflow-hidden rounded-md border border-slate-200">
      <MapContainer center={centre} zoom={placed.length > 1 ? 11 : 13}
        style={{ height: '100%', width: '100%' }}>
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <FitBounds points={placed} />

        {mode === 'heat'
          ? <HeatLayer points={placed} />
          : placed.map((point) => (
              <Marker key={point.id} position={[point.lat, point.lon]}
                icon={pinIcon(point.severity)}>
                <Popup>
                  <div className="min-w-[200px] space-y-1 text-[12px]">
                    <p className="font-mono text-[11px] font-medium text-slate-900">
                      {point.ticket_ref}
                    </p>
                    <p className="text-slate-700">{point.category || 'Unclassified'}</p>
                    <p className="text-slate-500">{point.department || 'No department'}</p>
                    <p className="text-slate-700">
                      {String(point.status || '').replace(/_/g, ' ')} · L{point.level} · {point.severity}
                    </p>
                    {point.overdue && <p className="font-medium text-red-700">Past TAT</p>}
                    <button onClick={() => onSelect?.(point.id)}
                      className="mt-1 w-full rounded-sm border border-blue-700 bg-blue-700 px-2 py-1 text-[11px] font-medium text-white hover:bg-blue-800">
                      Open complaint
                    </button>
                  </div>
                </Popup>
              </Marker>
            ))}
      </MapContainer>
    </div>
  );
}
