import { Delta } from './UI';

export default function KpiCard({ label, value, change, hint, icon: Icon, hero, invert }) {
  return (
    <div className={`card kpi ${hero ? 'kpi-hero' : ''}`}>
      <div className="kpi-label">{Icon && <Icon size={16} />}{label}</div>
      <div className="kpi-value">{value}</div>
      {change !== undefined && <Delta value={change} invert={invert} />}
      {hint && <div className="small muted">{hint}</div>}
    </div>
  );
}
