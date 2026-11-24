// Pure map helpers (no Leaflet import, so they run in Node tests).
export const SEVERITY_COLOR = {
  Critical: '#7f3f36',
  High: '#9d5145',
  Medium: '#967a3d',
  Low: '#557059',
};

export const HEAT_LEVELS = [
  { min: 4, color: '#7f3f36' },
  { min: 2, color: '#9d6347' },
  { min: 1, color: '#b89a58' },
];

export function severityColor(severity) {
  return SEVERITY_COLOR[severity] || '#27425f';
}

export function heatColor(count) {
  const level = HEAT_LEVELS.find((entry) => count >= entry.min);
  return (level || HEAT_LEVELS[HEAT_LEVELS.length - 1]).color;
}

/** Group points into ~1 km cells; returns averaged centres with counts + colour. */
export function heatCells(points, precision = 100) {
  const cells = new Map();

  points.forEach((point) => {
    if (point.lat == null || point.lon == null) return;
    const key = `${Math.round(point.lat * precision)}:${Math.round(point.lon * precision)}`;
    const cell = cells.get(key) || { key, lat: 0, lon: 0, count: 0 };
    cell.lat += point.lat;
    cell.lon += point.lon;
    cell.count += 1;
    cells.set(key, cell);
  });

  return [...cells.values()].map((cell) => ({
    key: cell.key,
    lat: cell.lat / cell.count,
    lon: cell.lon / cell.count,
    count: cell.count,
    color: heatColor(cell.count),
  }));
}
