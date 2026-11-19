import axios from 'axios';

export const TOKEN_KEY = 'insightflow_token';
export const BUSINESS_KEY = 'insightflow_business';
const api = axios.create({ baseURL: import.meta.env.VITE_API_URL || '/api', timeout: 30000 });

api.interceptors.request.use((cfg) => {
  const t = localStorage.getItem(TOKEN_KEY);
  if (t) cfg.headers.Authorization = `Bearer ${t}`;
  // Super admins can view another business; the server ignores this for everyone else.
  const biz = localStorage.getItem(BUSINESS_KEY);
  if (biz && !cfg.url.startsWith('/auth') && !cfg.url.startsWith('/admin')) cfg.params = { business_id: biz, ...(cfg.params || {}) };
  return cfg;
});

api.interceptors.response.use(
  (r) => r,
  (err) => {
    // An expired or revoked token while signed in: clear it and tell the app.
    if (err.response?.status === 401 && localStorage.getItem(TOKEN_KEY)) {
      localStorage.removeItem(TOKEN_KEY);
      localStorage.removeItem(BUSINESS_KEY);
      window.dispatchEvent(new CustomEvent('auth:expired', { detail: err.response?.data?.code }));
    }
    return Promise.reject(err);
  }
);

export const errMsg = (e) => {
  const apiMsg = e?.response?.data?.error;
  if (apiMsg) return apiMsg;
  const status = e?.response?.status;
  if (e?.code === 'ERR_NETWORK' || e?.code === 'ECONNABORTED' || [500, 502, 503, 504].includes(status)) {
    return 'Cannot reach the backend. Start it with "python run.py" in the backend folder (it must run on port 5000).';
  }
  return e?.message || 'Something went wrong';
};
export const fieldErrors = (e) => e?.response?.data?.fields || {};

export async function download(url, params, fallbackName) {
  const res = await api.get(url, { params, responseType: 'blob' });
  const cd = res.headers['content-disposition'] || '';
  const name = (cd.match(/filename="?([^"]+)"?/) || [])[1] || fallbackName;
  const href = URL.createObjectURL(res.data);
  const a = document.createElement('a');
  a.href = href; a.download = name; document.body.appendChild(a); a.click(); a.remove();
  URL.revokeObjectURL(href);
}

export default api;
