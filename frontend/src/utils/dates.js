const iso = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
export const PRESETS = [
  { id: '7d', label: '7 days', days: 7 }, { id: '30d', label: '30 days', days: 30 },
  { id: '90d', label: '90 days', days: 90 }, { id: '12m', label: '12 months', days: 365 },
  { id: 'ytd', label: 'Year to date' }, { id: 'all', label: 'All time' }, { id: 'custom', label: 'Custom' },
];
export function presetRange(id) {
  const end = new Date(); const start = new Date();
  if (id === 'ytd') start.setMonth(0, 1);
  else if (id === 'all') start.setFullYear(end.getFullYear() - 10);
  else start.setDate(end.getDate() - ((PRESETS.find((p) => p.id === id)?.days || 30) - 1));
  return { start: iso(start), end: iso(end) };
}
export const makeRange = (id = '30d') => ({ preset: id, ...presetRange(id) });
export { iso };
