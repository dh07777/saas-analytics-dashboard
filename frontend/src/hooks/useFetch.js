import { useCallback, useEffect, useRef, useState } from 'react';
import api, { errMsg } from '../api/client';

/** GET helper. `params` is serialised so inline objects do not retrigger the effect. */
export default function useFetch(url, params = {}, { enabled = true } = {}) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(enabled);
  const [error, setError] = useState(null);
  const key = JSON.stringify([url, params]);
  const seq = useRef(0);

  const load = useCallback(async () => {
    if (!enabled) return;
    const id = ++seq.current;
    setLoading(true); setError(null);
    try {
      const r = await api.get(url, { params: JSON.parse(key)[1] });
      if (id === seq.current) setData(r.data);
    } catch (e) {
      if (id === seq.current) setError(errMsg(e));
    } finally {
      if (id === seq.current) setLoading(false);
    }
  }, [key, enabled, url]);

  useEffect(() => { load(); }, [load]);
  return { data, loading, error, reload: load };
}
