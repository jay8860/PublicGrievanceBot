// Loading / empty / error states.
import React from 'react';
import { AlertCircle, CheckCircle2, Inbox, Loader2 } from 'lucide-react';
import { cls } from '../lib/utils';

export function Spinner({ size = 16, className = '' }) {
  return <Loader2 size={size} className={cls('animate-spin text-blue-600', className)} />;
}

export function LoadingBlock({ label = 'Loading…' }) {
  return (
    <div className="flex items-center justify-center gap-2 py-12 text-sm text-slate-500">
      <Spinner /> {label}
    </div>
  );
}

export function EmptyState({ title = 'Nothing here yet', message, icon: Icon = Inbox, action }) {
  return (
    <div className="flex flex-col items-center justify-center gap-1.5 py-10 px-6 text-center">
      <Icon size={20} className="text-slate-300" />
      <p className="text-[12px] font-medium text-slate-700">{title}</p>
      {message && <p className="text-[11px] text-slate-500 max-w-sm">{message}</p>}
      {action}
    </div>
  );
}

export function ErrorState({ message, onRetry }) {
  return (
    <div className="flex flex-col items-center gap-1.5 py-10 px-6 text-center">
      <AlertCircle size={20} className="text-red-600" />
      <p className="text-[12px] font-medium text-slate-800">Could not load this data</p>
      <p className="text-[11px] text-slate-500 max-w-md">{message}</p>
      {onRetry && (
        <button onClick={onRetry} className="mt-1 text-[11px] font-medium text-blue-700 hover:underline">
          Try again
        </button>
      )}
    </div>
  );
}

export function InlineAlert({ tone = 'info', children }) {
  const tones = {
    info: 'bg-blue-50 border-blue-200 text-blue-800',
    success: 'bg-emerald-50 border-emerald-200 text-emerald-800',
    warning: 'bg-amber-50 border-amber-200 text-amber-800',
    danger: 'bg-red-50 border-red-200 text-red-800',
  };
  const Icon = tone === 'success' ? CheckCircle2 : AlertCircle;
  return (
    <div className={cls('flex items-start gap-2 rounded-md border px-2.5 py-2 text-[11px]', tones[tone])}>
      <Icon size={13} className="mt-0.5 shrink-0" />
      <div>{children}</div>
    </div>
  );
}

