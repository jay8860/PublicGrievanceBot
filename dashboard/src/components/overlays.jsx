// Modal, confirm dialog, tabs and pagination.
import React, { useEffect } from 'react';
import { ChevronLeft, ChevronRight, X } from 'lucide-react';
import { cls } from '../lib/utils';
import { Button } from './controls';

export function Modal({ open, onClose, title, subtitle, children, footer, width = 'max-w-2xl' }) {
  useEffect(() => {
    if (!open) return undefined;
    const onKey = (e) => { if (e.key === 'Escape') onClose?.(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-slate-900/50 p-4 sm:p-8">
      <div className={cls('w-full bg-white rounded-lg shadow-md border border-slate-200 my-auto', width)}>
        <div className="flex items-start justify-between gap-4 px-4 py-3 border-b border-slate-200">
          <div>
            <h3 className="text-[14px] font-semibold text-slate-900">{title}</h3>
            {subtitle && <p className="text-[11px] text-slate-500 mt-0.5">{subtitle}</p>}
          </div>
          <button onClick={onClose} className="p-1 rounded-sm text-slate-400 hover:bg-slate-100">
            <X size={17} />
          </button>
        </div>
        <div className="px-4 py-3 max-h-[70vh] overflow-y-auto">{children}</div>
        {footer && (
          <div className="px-4 py-2.5 border-t border-slate-200 bg-slate-50 rounded-b-lg flex justify-end gap-2">
            {footer}
          </div>
        )}
      </div>

    </div>
  );
}

export function ConfirmDialog({ open, title, message, confirmLabel = 'Confirm', tone = 'danger',
  loading, onConfirm, onCancel }) {
  return (
    <Modal open={open} onClose={onCancel} title={title} width="max-w-md"
      footer={(
        <>
          <Button variant="secondary" onClick={onCancel}>Cancel</Button>
          <Button variant={tone === 'danger' ? 'danger' : 'primary'} loading={loading} onClick={onConfirm}>
            {confirmLabel}
          </Button>
        </>
      )}>
      <p className="text-sm text-slate-600">{message}</p>
    </Modal>
  );
}

export function Tabs({ tabs, value, onChange }) {
  return (
    <div className="flex flex-wrap gap-1 border-b border-slate-200">
      {tabs.map((tab) => {
        const active = tab.value === value;
        return (
          <button key={tab.value} onClick={() => onChange(tab.value)}
            className={cls('-mb-px px-3 py-2 text-sm font-medium border-b-2 transition',
              active ? 'border-blue-700 text-blue-800'
                : 'border-transparent text-slate-500 hover:text-slate-700')}>
            {tab.label}
            {tab.count !== undefined && (
              <span className={cls('ml-1.5 rounded-sm px-1 py-0.5 text-[10px] tabular-nums',
                active ? 'bg-blue-100 text-blue-800' : 'bg-slate-100 text-slate-500')}>
                {tab.count}
              </span>
            )}

          </button>
        );
      })}
    </div>
  );
}

export function Pagination({ page, pageSize, total, onPageChange }) {
  const pages = Math.max(1, Math.ceil(total / pageSize));
  if (total === 0) return null;
  return (
    <div className="flex flex-wrap items-center justify-between gap-2 px-4 py-2.5 border-t border-slate-200 text-[11px] text-slate-500">
      <span>
        Showing <b>{(page - 1) * pageSize + 1}</b>–<b>{Math.min(page * pageSize, total)}</b>
        {' '}of <b>{total}</b>
      </span>
      <div className="flex items-center gap-1">
        <Button variant="secondary" size="sm" disabled={page <= 1} onClick={() => onPageChange(page - 1)}>
          <ChevronLeft size={14} /> Prev
        </Button>
        <span className="px-2">Page {page} / {pages}</span>
        <Button variant="secondary" size="sm" disabled={page >= pages} onClick={() => onPageChange(page + 1)}>
          Next <ChevronRight size={14} />
        </Button>
      </div>
    </div>
  );
}
