import { useState } from 'react';
import { Info } from '../icons';
import { TrendChart } from '../components/charts';
import DataTable from '../components/DataTable';
import DateRange from '../components/DateRange';
import KpiCard from '../components/KpiCard';
import { Async, Delta, PageHead } from '../components/UI';
import useFetch from '../hooks/useFetch';
import useFormat from '../hooks/useFormat';
import { makeRange } from '../utils/dates';

const GRANS = [['daily', 'Daily'], ['weekly', 'Weekly'], ['monthly', 'Monthly'], ['yearly', 'Yearly']];

export default function Revenue() {
  const f = useFormat();
  const [range, setRange] = useState(makeRange('12m')); const [gran, setGran] = useState('monthly'); const [months, setMonths] = useState(3);
  const { data, loading, error, reload } = useFetch('/analytics/revenue', { start: range.start, end: range.end, granularity: gran, forecast_months: months });
  const fc = data?.forecast;
  const chartData = fc ? [...fc.history.map((h) => ({ period: h.period, actual: h.revenue })),
    ...fc.forecast.map((p) => ({ period: p.period, forecast: p.forecast, lower: p.lower, upper: p.upper }))] : [];
  if (fc?.history.length && fc.forecast.length) chartData[fc.history.length - 1].forecast = fc.history[fc.history.length - 1].revenue;
  const cmp = data?.comparison;

  return (
    <>
      <PageHead title="Revenue analytics" subtitle="Revenue, profit and growth from completed orders.">
        <DateRange value={range} onChange={setRange} presets={['30d', '90d', '12m', 'ytd', 'all', 'custom']} />
        <div className="seg" role="group" aria-label="Granularity">{GRANS.map(([id, l]) => <button key={id} className={gran === id ? 'on' : ''} onClick={() => setGran(id)}>{l}</button>)}</div>
      </PageHead>
      <Async loading={loading && !data} error={error} onRetry={reload} rows={8}>
        {data && (<>
          <div className="grid g-4">
            <KpiCard label="Revenue" value={f.money(cmp.revenue.current)} change={cmp.revenue.change_pct} hint="vs previous period" hero />
            <KpiCard label="Gross profit" value={f.money(cmp.gross_profit.current)} change={cmp.gross_profit.change_pct} />
            <KpiCard label="Expenses" value={f.money(cmp.expenses.current)} change={cmp.expenses.change_pct} invert />
            <KpiCard label="Net profit" value={f.money(cmp.profit.current)} change={cmp.profit.change_pct} />
          </div>
          <div className="card" style={{ marginBottom: 16 }}>
            <div className="card-head"><h2>{GRANS.find((g) => g[0] === gran)[1]} revenue and profit</h2></div>
            {data.series.length ? <TrendChart data={data.series} type="composed" series={[{ key: 'revenue', name: 'Revenue', as: 'bar' }, { key: 'gross_profit', name: 'Gross profit', color: '#4caf7a' }, { key: 'profit', name: 'Net profit', color: '#e8a317' }]} />
              : <p className="muted">No data in this range. Try a longer period.</p>}
          </div>
          <div className="card" style={{ marginBottom: 16 }}>
            <div className="card-head"><h2>Revenue forecast</h2>
              <div className="seg" role="group" aria-label="Forecast months">{[3, 6, 12].map((m) => <button key={m} className={months === m ? 'on' : ''} onClick={() => setMonths(m)}>{m} months</button>)}</div></div>
            {fc.forecast.length ? (<>
              <TrendChart data={chartData} type="composed" series={[{ key: 'actual', name: 'Actual', as: 'bar' }, { key: 'forecast', name: 'Forecast', color: '#e8a317' }, { key: 'upper', name: 'Upper range', color: '#c2703d' }, { key: 'lower', name: 'Lower range', color: '#5b6ee1' }]} />
              <p className="small muted" style={{ display: 'flex', gap: 6 }}><Info size={15} />{fc.meta.method} ({fc.meta.months_used} months, trend {f.money(fc.meta.monthly_trend)}/month{fc.meta.r2 != null ? `, R² ${fc.meta.r2}` : ''}). The range shows ±1.96 standard deviations of past error. Forecasts are estimates, not guarantees.</p>
            </>) : <p className="muted">{fc.meta.note || 'Not enough history to forecast yet.'}</p>}
          </div>
          <div className="card"><div className="card-head"><h2>Period breakdown</h2></div>
            <DataTable rows={[...data.series].reverse()} rowKey="period" emptyTitle="No periods to show" columns={[
              { key: 'period', label: 'Period' }, { key: 'orders', label: 'Orders', align: 'right' },
              { key: 'revenue', label: 'Revenue', align: 'right', render: (r) => f.money(r.revenue) },
              { key: 'growth_pct', label: 'Growth', align: 'right', render: (r) => <Delta value={r.growth_pct == null ? null : Math.round(r.growth_pct * 10) / 10} /> },
              { key: 'expenses', label: 'Expenses', align: 'right', render: (r) => f.money(r.expenses) },
              { key: 'profit', label: 'Net profit', align: 'right', render: (r) => <span className={r.profit < 0 ? 'bad' : ''}>{f.money(r.profit)}</span> }]} />
          </div>
        </>)}
      </Async>
    </>
  );
}
