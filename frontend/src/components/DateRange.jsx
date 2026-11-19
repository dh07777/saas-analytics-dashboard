import { PRESETS, presetRange } from '../utils/dates';

export default function DateRange({ value, onChange, presets }) {
  const list = presets ? PRESETS.filter((p) => presets.includes(p.id)) : PRESETS;
  return (
    <div className="toolbar no-print">
      <div className="seg" role="group" aria-label="Date range">
        {list.map((p) => (
          <button key={p.id} className={value.preset === p.id ? 'on' : ''}
            onClick={() => onChange(p.id === 'custom' ? { ...value, preset: 'custom' } : { preset: p.id, ...presetRange(p.id) })}>{p.label}</button>
        ))}
      </div>
      {value.preset === 'custom' && (
        <>
          <input className="input" type="date" aria-label="Start date" style={{ width: 150 }} value={value.start} max={value.end}
            onChange={(e) => onChange({ ...value, start: e.target.value })} />
          <input className="input" type="date" aria-label="End date" style={{ width: 150 }} value={value.end} min={value.start}
            onChange={(e) => onChange({ ...value, end: e.target.value })} />
        </>
      )}
    </div>
  );
}
