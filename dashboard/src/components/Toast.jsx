// Toast notifications (success / error) used by every action.
import React, { createContext, useCallback, useContext, useState } from 'react';
import { AlertCircle, CheckCircle2, Info, X } from 'lucide-react';
import { cls } from '../lib/utils';

const ToastContext = createContext({ push: () => {} });

const TONES = {
  success: ['border-l-emerald-600', CheckCircle2, 'text-emerald-700'],
  error: ['border-l-red-600', AlertCircle, 'text-red-700'],
  info: ['border-l-blue-700', Info, 'text-blue-700'],
};

export function ToastProvider({ children }) {
  const [items, setItems] = useState([]);

  const remove = useCallback((id) => {
    setItems((current) => current.filter((item) => item.id !== id));
  }, []);

  const push = useCallback((message, tone = 'success') => {
    const id = `${Date.now()}-${Math.random().toString(16).slice(2)}`;
    setItems((current) => [...current, { id, message, tone }]);
    setTimeout(() => remove(id), 4500);
  }, [remove]);

  return (
    <ToastContext.Provider value={{ push }}>
      {children}
      <div className="fixed bottom-4 right-4 z-[60] flex w-full max-w-sm flex-col gap-2">
        {items.map((item) => {
          const [border, Icon, iconColor] = TONES[item.tone] || TONES.info;
          return (
            <div key={item.id}
              className={cls('flex items-start gap-2 rounded-md border border-slate-200 border-l-2 bg-white px-3 py-2 shadow-md', border)}>
              <Icon size={14} className={cls('mt-0.5 shrink-0', iconColor)} />
              <p className="flex-1 text-[11px] text-slate-700">{item.message}</p>
              <button onClick={() => remove(item.id)} className="text-slate-400 hover:text-slate-600">
                <X size={13} />
              </button>
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
}


export function useToast() {
  return useContext(ToastContext);
}
