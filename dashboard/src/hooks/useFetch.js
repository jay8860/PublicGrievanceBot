// Tiny data-fetching hook with loading / error / reload semantics.
import { useCallback, useEffect, useRef, useState } from 'react';
import { apiErrorMessage } from '../services/apiV2';

export function useFetch(loader, deps = [], { enabled = true } = {}) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(enabled);
  const [error, setError] = useState('');
  const [nonce, setNonce] = useState(0);
  const loaderRef = useRef(loader);
  loaderRef.current = loader;

  useEffect(() => {
    if (!enabled) {
      setLoading(false);
      return undefined;
    }
    let alive = true;
    setLoading(true);
    setError('');
    loaderRef.current()
      .then((payload) => { if (alive) { setData(payload); setLoading(false); } })
      .catch((err) => {
        if (alive) { setError(apiErrorMessage(err)); setLoading(false); }
      });
    return () => { alive = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, nonce, enabled]);

  const reload = useCallback(() => setNonce((n) => n + 1), []);
  return { data, loading, error, reload, setData };
}
