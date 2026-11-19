import { useMemo } from 'react';
import { useAuth } from '../contexts/AuthContext';

export function formatDate(value, fmt = 'YYYY-MM-DD') {
  if (!value) return '—';
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return String(value);
  const yyyy = d.getFullYear(); const mm = String(d.getMonth() + 1).padStart(2, '0'); const dd = String(d.getDate()).padStart(2, '0');
  return fmt === 'DD/MM/YYYY' ? `${dd}/${mm}/${yyyy}` : fmt === 'MM/DD/YYYY' ? `${mm}/${dd}/${yyyy}` : `${yyyy}-${mm}-${dd}`;
}

export function makeFormatters(currency = 'USD', dateFmt = 'YYYY-MM-DD') {
  const money = new Intl.NumberFormat(undefined, { style: 'currency', currency, maximumFractionDigits: 2 });
  const compact = new Intl.NumberFormat(undefined, { style: 'currency', currency, notation: 'compact', maximumFractionDigits: 1 });
  const num = new Intl.NumberFormat();
  return {
    money: (v) => (v == null ? '—' : money.format(v)),
    compact: (v) => (v == null ? '—' : compact.format(v)),
    num: (v) => (v == null ? '—' : num.format(v)),
    pct: (v) => (v == null ? '—' : `${v > 0 ? '+' : ''}${v}%`),
    date: (v) => formatDate(v, dateFmt),
    dateTime: (v) => (v ? `${formatDate(v, dateFmt)} ${new Date(v.endsWith?.('Z') ? v : `${v}Z`).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}` : '—'),
  };
}

export default function useFormat() {
  const { user } = useAuth();
  const cur = user?.business?.currency; const df = user?.settings?.date_format;
  return useMemo(() => makeFormatters(cur || 'USD', df || 'YYYY-MM-DD'), [cur, df]);
}
