import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import api, { BUSINESS_KEY, TOKEN_KEY } from '../api/client';
import { useTheme } from './ThemeContext';
import { useToast } from './ToastContext';

const AuthCtx = createContext(null);
export const useAuth = () => useContext(AuthCtx);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(!!localStorage.getItem(TOKEN_KEY));
  const { setTheme } = useTheme();
  const toast = useToast();

  const apply = useCallback((u) => {
    setUser(u);
    if (u?.settings?.theme) setTheme(u.settings.theme);
  }, [setTheme]);

  useEffect(() => {
    if (!localStorage.getItem(TOKEN_KEY)) return;
    api.get('/auth/me').then((r) => apply(r.data.user)).catch(() => localStorage.removeItem(TOKEN_KEY)).finally(() => setLoading(false));
  }, [apply]);

  useEffect(() => {
    const onExpired = (e) => {
      setUser(null);
      toast.info(e.detail === 'token_expired' ? 'Your session expired. Please sign in again.' : 'You were signed out. Please sign in again.');
    };
    window.addEventListener('auth:expired', onExpired);
    return () => window.removeEventListener('auth:expired', onExpired);
  }, [toast]);

  const start = useCallback((data) => { localStorage.setItem(TOKEN_KEY, data.token); apply(data.user); return data.user; }, [apply]);
  const login = useCallback(async (email, password) => start((await api.post('/auth/login', { email, password })).data), [start]);
  const register = useCallback(async (payload) => start((await api.post('/auth/register', payload)).data), [start]);
  const logout = useCallback(async () => {
    try { await api.post('/auth/logout'); } catch { /* token may already be invalid */ }
    localStorage.removeItem(TOKEN_KEY); localStorage.removeItem(BUSINESS_KEY); setUser(null);
  }, []);
  const refresh = useCallback(async () => apply((await api.get('/auth/me')).data.user), [apply]);
  const can = useCallback((perm) => !!user?.permissions?.includes(perm), [user]);

  const value = useMemo(() => ({ user, loading, login, register, logout, refresh, can, setUser: apply }),
    [user, loading, login, register, logout, refresh, can, apply]);
  return <AuthCtx.Provider value={value}>{children}</AuthCtx.Provider>;
}
