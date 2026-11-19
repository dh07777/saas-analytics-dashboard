import { Area, AreaChart, Bar, BarChart, CartesianGrid, ComposedChart, Legend, Line, LineChart, Pie, PieChart, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import useFormat from '../hooks/useFormat';

export const COLORS = ['#167a8e', '#e8a317', '#5b6ee1', '#d9576b', '#4caf7a', '#8e7cc3', '#c2703d', '#3aa7a0'];

function Tip({ active, payload, label, fmt, names }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="tooltip">
      <strong>{label ?? payload[0].name}</strong>
      {payload.map((p) => <div key={p.dataKey || p.name} style={{ color: p.color || p.payload?.fill }}>{names?.[p.dataKey] || p.name}: {typeof p.value === 'number' ? (fmt || ((x) => x))(p.value, p.dataKey) : p.value}</div>)}
    </div>
  );
}

const axis = { tick: { fill: 'currentColor', fontSize: 12 }, stroke: 'currentColor', tickLine: false };

export function TrendChart({ data, x = 'period', series, height, money = true, type = 'area' }) {
  const f = useFormat();
  const fmt = money ? f.money : f.num;
  const names = Object.fromEntries(series.map((s) => [s.key, s.name]));
  const Chart = type === 'bar' ? BarChart : type === 'composed' ? ComposedChart : AreaChart;
  return (
    <div className={`chart ${height === 'sm' ? 'sm' : ''}`} role="img" aria-label="Trend chart">
      <ResponsiveContainer>
        <Chart data={data} margin={{ left: 4, right: 8, top: 8 }}>
          <CartesianGrid vertical={false} />
          <XAxis dataKey={x} {...axis} minTickGap={24} />
          <YAxis {...axis} width={58} tickFormatter={(v) => (money ? f.compact(v) : f.num(v))} />
          <Tooltip content={<Tip fmt={fmt} names={names} />} />
          {series.length > 1 && <Legend />}
          {series.map((s, i) => {
            const color = s.color || COLORS[i % COLORS.length];
            if (type === 'bar' || (type === 'composed' && s.as === 'bar')) return <Bar key={s.key} dataKey={s.key} name={s.name} fill={color} radius={[3, 3, 0, 0]} />;
            if (type === 'composed') return <Line key={s.key} dataKey={s.key} name={s.name} stroke={color} strokeWidth={2.5} dot={false} />;
            return <Area key={s.key} dataKey={s.key} name={s.name} stroke={color} fill={color} fillOpacity={0.15} strokeWidth={2.5} />;
          })}
        </Chart>
      </ResponsiveContainer>
    </div>
  );
}

export function LineSeries({ data, x = 'period', series, money = false }) {
  const f = useFormat();
  return (
    <div className="chart" role="img" aria-label="Line chart">
      <ResponsiveContainer>
        <LineChart data={data} margin={{ left: 4, right: 8, top: 8 }}>
          <CartesianGrid vertical={false} /><XAxis dataKey={x} {...axis} /><YAxis {...axis} width={50} />
          <Tooltip content={<Tip fmt={money ? f.money : f.num} />} /><Legend />
          {series.map((s, i) => <Line key={s.key} dataKey={s.key} name={s.name} stroke={s.color || COLORS[i]} strokeWidth={2.5} dot={false} strokeDasharray={s.dashed ? '5 4' : undefined} />)}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

export function BarList({ data, label, value, money = true, height = 'sm', horizontal = true }) {
  const f = useFormat();
  return (
    <div className={`chart ${height === 'sm' ? 'sm' : ''}`} role="img" aria-label="Bar chart" style={horizontal ? { height: Math.max(180, data.length * 34 + 20) } : undefined}>
      <ResponsiveContainer>
        <BarChart data={data} layout={horizontal ? 'vertical' : 'horizontal'} margin={{ left: 8, right: 16 }}>
          <CartesianGrid horizontal={!horizontal} vertical={horizontal} />
          {horizontal ? <><XAxis type="number" {...axis} tickFormatter={money ? f.compact : f.num} /><YAxis type="category" dataKey={label} width={120} {...axis} /></>
            : <><XAxis dataKey={label} {...axis} /><YAxis {...axis} width={58} tickFormatter={money ? f.compact : f.num} /></>}
          <Tooltip content={<Tip fmt={money ? f.money : f.num} />} cursor={{ fill: 'rgba(127,127,127,0.1)' }} />
          <Bar dataKey={value} name={value} fill={COLORS[0]} radius={horizontal ? [0, 3, 3, 0] : [3, 3, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export function Donut({ data, label, value, money = true }) {
  const f = useFormat();
  const total = data.reduce((s, d) => s + d[value], 0) || 1;
  return (
    <div style={{ display: 'grid', gap: 8 }}>
      <div className="chart sm" role="img" aria-label="Distribution chart">
        <ResponsiveContainer>
          <PieChart>
            <Pie data={data} dataKey={value} nameKey={label} innerRadius="58%" outerRadius="88%" paddingAngle={2} stroke="none">
              {data.map((d, i) => <Cell key={d[label]} fill={COLORS[i % COLORS.length]} />)}
            </Pie>
            <Tooltip content={<Tip fmt={money ? f.money : f.num} />} />
          </PieChart>
        </ResponsiveContainer>
      </div>
      <div style={{ display: 'grid', gap: 4 }}>
        {data.map((d, i) => (
          <div key={d[label]} className="small" style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <span style={{ width: 10, height: 10, borderRadius: 2, background: COLORS[i % COLORS.length] }} />
            <span style={{ flex: 1 }}>{d[label]}</span><span className="muted">{Math.round((d[value] / total) * 100)}%</span>
          </div>))}
      </div>
    </div>
  );
}
