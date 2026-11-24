// Cards, stat tiles and status stamps. Quiet chrome, one accent.
import React from 'react';
import { cls, titleCase } from '../lib/utils';

export { cls };

export function Card({ className = '', children }) {
  return (
    <div className={cls('bg-white rounded-lg border border-slate-200 shadow-sm', className)}>
      {children}
    </div>
  );
}

export function CardHeader({ title, subtitle, actions }) {
  return (
    <div className="flex items-start justify-between gap-3 px-4 py-3 border-b border-slate-200">
      <div>
        <h3 className="text-[13px] font-semibold text-slate-800">{title}</h3>
        {subtitle && <p className="text-[11px] text-slate-500 mt-0.5">{subtitle}</p>}
      </div>
      {actions}
    </div>
  );
}

const ICON_TONES = {
  navy: 'text-blue-700', blue: 'text-blue-600', green: 'text-emerald-600',
  amber: 'text-amber-600', red: 'text-red-600', slate: 'text-slate-500',
  violet: 'text-violet-600',
};

export function StatCard({ label, value, hint, tone = 'blue', icon: Icon, onClick }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cls('text-left bg-white rounded-lg border border-slate-200 shadow-sm px-4 py-3',
        onClick && 'hover:border-slate-300 hover:bg-slate-50')}
    >
      <div className="flex items-start justify-between gap-2">
        <p className="text-[11px] text-slate-500">{label}</p>
        {Icon && <Icon size={14} strokeWidth={1.75} className={ICON_TONES[tone] || ICON_TONES.blue} />}
      </div>
      <p className="mt-1.5 text-[22px] leading-7 font-semibold text-slate-900 tabular-nums">
        {value ?? '—'}
      </p>
      {hint && <p className="text-[11px] text-slate-500">{hint}</p>}
    </button>
  );
}

const STAMP = 'inline-flex items-center px-1.5 py-0.5 rounded-sm border text-[11px] font-medium';

const STATUS_STYLES = {
  NEW: 'bg-sky-50 text-sky-700 border-sky-200',
  ASSIGNED: 'bg-blue-50 text-blue-700 border-blue-200',
  ACKNOWLEDGED: 'bg-indigo-50 text-indigo-700 border-indigo-200',
  IN_PROGRESS: 'bg-amber-50 text-amber-700 border-amber-200',
  ESCALATED: 'bg-orange-50 text-orange-700 border-orange-200',
  RESOLVED: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  VERIFIED: 'bg-emerald-50 text-emerald-800 border-emerald-300',
  CLOSED: 'bg-slate-100 text-slate-600 border-slate-200',
  REOPENED: 'bg-red-50 text-red-700 border-red-200',
  NEEDS_REVIEW: 'bg-violet-50 text-violet-700 border-violet-200',
};

export function StatusBadge({ status }) {
  if (!status) return <span className="text-slate-400">—</span>;
  return (
    <span className={cls(STAMP, STATUS_STYLES[status] || 'bg-slate-100 text-slate-600 border-slate-200')}>
      {titleCase(status)}
    </span>
  );
}

const SEVERITY_STYLES = {
  High: 'bg-red-50 text-red-700 border-red-200',
  Critical: 'bg-red-100 text-red-800 border-red-300',
  Medium: 'bg-amber-50 text-amber-700 border-amber-200',
  Low: 'bg-slate-100 text-slate-600 border-slate-200',
};

export function SeverityBadge({ severity }) {
  const value = severity || 'Medium';
  return (
    <span className={cls(STAMP, SEVERITY_STYLES[value] || SEVERITY_STYLES.Medium)}>{value}</span>
  );
}

export function LevelBadge({ level }) {
  const styles = {
    1: 'bg-blue-50 text-blue-700 border-blue-200',
    2: 'bg-indigo-50 text-indigo-700 border-indigo-200',
    3: 'bg-violet-50 text-violet-700 border-violet-200',
    4: 'bg-slate-800 text-white border-slate-800',
  };
  return (
    <span className={cls(STAMP, 'font-mono', styles[level] || styles[1])}>L{level || 1}</span>
  );
}

export function VerificationBadge({ verdict }) {
  const map = {
    verified: ['Verified', 'bg-emerald-50 text-emerald-700 border-emerald-200'],
    requires_review: ['Manual review', 'bg-amber-50 text-amber-700 border-amber-200'],
    failed: ['Failed', 'bg-red-50 text-red-700 border-red-200'],
  };
  const [label, style] = map[verdict] || ['Pending', 'bg-slate-100 text-slate-600 border-slate-200'];
  return <span className={cls(STAMP, style)}>{label}</span>;
}

export function TelegramBadge({ status }) {
  const map = {
    connected: ['Connected', 'bg-emerald-50 text-emerald-700 border-emerald-200'],
    pending: ['Invite pending', 'bg-amber-50 text-amber-700 border-amber-200'],
    revoked: ['Access revoked', 'bg-red-50 text-red-700 border-red-200'],
    none: ['Not connected', 'bg-slate-100 text-slate-600 border-slate-200'],
  };
  const [label, style] = map[status] || map.none;
  return <span className={cls(STAMP, style)}>{label}</span>;
}

