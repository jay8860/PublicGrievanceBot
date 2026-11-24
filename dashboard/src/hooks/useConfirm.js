// Promise-based confirmation dialog: `const ok = await confirm({...})`.
import { useCallback, useState } from 'react';

export function useConfirmDialog() {
  const [request, setRequest] = useState(null);

  const confirm = useCallback((options) => new Promise((resolve) => {
    setRequest({ ...options, resolve });
  }), []);

  const close = (result) => {
    request?.resolve(result);
    setRequest(null);
  };

  const dialog = {
    open: Boolean(request),
    title: request?.title || 'Confirm',
    message: request?.message || '',
    confirmLabel: request?.confirmLabel || 'Confirm',
    tone: request?.tone || 'danger',
    onCancel: () => close(false),
    onConfirm: () => close(true),
  };

  return { confirm, dialog };
}

