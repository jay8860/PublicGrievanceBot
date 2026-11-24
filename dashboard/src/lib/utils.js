// Small helpers shared by every page.

export function decodeToken(token) {
  if (!token) return null;
  try {
    const payload = token.split('.')[1];
    const normalised = payload.replace(/-/g, '+').replace(/_/g, '/');
    const json = decodeURIComponent(
      atob(normalised + '='.repeat((4 - (normalised.length % 4)) % 4))
        .split('')
        .map((c) => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
        .join('')
    );
    return JSON.parse(json);
  } catch {
    return null;
  }
}

export function roleOf(token) {
  const claims = decodeToken(token) || {};
  return claims.role || 'admin'; // legacy tokens carry no role -> dashboard admin
}

export const ROLES = {
  superadmin: 'Super Admin',
  admin: 'Administrator',
  viewer: 'Viewer',
  officer: 'Officer',
};

export function canManage(token) {
  return ['superadmin', 'admin'].includes(roleOf(token));
}

export function isSuperadmin(token) {
  return roleOf(token) === 'superadmin';
}

export function fmtDate(value) {
  if (!value) return '—';
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return '—';
  return d.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' });
}

export function fmtDateTime(value) {
  if (!value) return '—';
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return '—';
  return d.toLocaleString('en-IN', {
    day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit',
  });
}

export function relativeTime(value) {
  if (!value) return '—';
  const then = new Date(value).getTime();
  if (Number.isNaN(then)) return '—';
  const diff = Date.now() - then;
  const mins = Math.round(diff / 60000);
  if (Math.abs(mins) < 60) return `${mins}m ago`;
  const hours = Math.round(mins / 60);
  if (Math.abs(hours) < 24) return `${hours}h ago`;
  const days = Math.round(hours / 24);
  return `${days}d ago`;
}

export function minutesLabel(minutes) {
  if (minutes === null || minutes === undefined) return '—';
  const abs = Math.abs(minutes);
  const text = abs >= 1440
    ? `${Math.floor(abs / 1440)}d ${Math.floor((abs % 1440) / 60)}h`
    : abs >= 60 ? `${Math.floor(abs / 60)}h ${abs % 60}m` : `${abs}m`;
  return minutes < 0 ? `overdue ${text}` : `${text} left`;
}

export function hours(value) {
  if (value === null || value === undefined) return '—';
  return `${Number(value).toFixed(1)} h`;
}

export function initials(name = '') {
  return name.split(' ').filter(Boolean).slice(0, 2).map((p) => p[0].toUpperCase()).join('');
}

export function titleCase(value = '') {
  return String(value).toLowerCase().replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

export function cls(...parts) {
  return parts.filter(Boolean).join(' ');
}

export const STATUS_OPTIONS = [
  'NEW', 'ASSIGNED', 'ACKNOWLEDGED', 'IN_PROGRESS', 'ESCALATED',
  'RESOLVED', 'VERIFIED', 'CLOSED', 'REOPENED', 'NEEDS_REVIEW',
];

export const LEVEL_OPTIONS = [1, 2, 3, 4];
export const SEVERITY_OPTIONS = ['High', 'Medium', 'Low'];

export function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}
