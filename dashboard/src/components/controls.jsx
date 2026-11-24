// Buttons and form controls.
import React from 'react';
import { Search, X } from 'lucide-react';
import { cls } from '../lib/utils';
import { Spinner } from './feedback';

const VARIANTS = {
  primary: 'bg-blue-700 hover:bg-blue-800 text-white border-blue-700',
  navy: 'bg-blue-900 hover:bg-blue-950 text-white border-blue-900',
  secondary: 'bg-white hover:bg-slate-50 text-slate-700 border-slate-300',
  ghost: 'bg-transparent hover:bg-slate-100 text-slate-600 border-transparent',
  danger: 'bg-red-600 hover:bg-red-700 text-white border-red-600',
  success: 'bg-emerald-600 hover:bg-emerald-700 text-white border-emerald-600',
};

export function Button({ variant = 'primary', size = 'md', loading = false, disabled,
  className = '', children, ...props }) {
  const sizes = { sm: 'px-2.5 py-1.5 text-[11px]', md: 'px-3 py-1.5 text-[12px]', lg: 'px-3.5 py-2 text-[13px]' };
  return (
    <button {...props} disabled={disabled || loading}
      className={cls('inline-flex items-center justify-center gap-1.5 rounded-md border font-medium',
        sizes[size], VARIANTS[variant] || VARIANTS.primary,
        (disabled || loading) && 'opacity-55 cursor-not-allowed', className)}>
      {loading && <Spinner size={13} className="text-current" />}
      {children}
    </button>
  );
}

export function Field({ label, hint, error, required, children }) {
  return (
    <label className="block">
      {label && (
        <span className="block text-[11px] font-medium text-slate-600 mb-1">
          {label}{required && <span className="text-red-600"> *</span>}
        </span>
      )}
      {children}
      {error ? <span className="block text-[11px] text-red-700 mt-1">{error}</span>
        : hint ? <span className="block text-[11px] text-slate-500 mt-1">{hint}</span> : null}
    </label>
  );
}

const CONTROL = 'w-full rounded-md border border-slate-300 bg-white px-2.5 py-1.5 text-[12px] text-slate-800 ' +
  'placeholder-slate-400 focus:outline-none focus:border-blue-600 focus:ring-2 focus:ring-blue-600/15 disabled:bg-slate-50 disabled:text-slate-500';


export function Input({ className = '', ...props }) {
  return <input {...props} className={cls(CONTROL, className)} />;
}

export function Textarea({ className = '', rows = 3, ...props }) {
  return <textarea rows={rows} {...props} className={cls(CONTROL, className)} />;
}

export function Select({ className = '', children, ...props }) {
  return <select {...props} className={cls(CONTROL, 'pr-8', className)}>{children}</select>;
}

export function SearchInput({ value, onChange, placeholder = 'Search…', className = '' }) {
  return (
    <div className={cls('relative', className)}>
      <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
      <input value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder}
        className={cls(CONTROL, 'pl-9')} />
      {value && (
        <button type="button" onClick={() => onChange('')}
          className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600">
          <X size={14} />
        </button>
      )}
    </div>
  );
}
