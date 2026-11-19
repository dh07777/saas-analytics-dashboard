import { useState } from 'react';
import { TrendChart, Donut } from '../components/charts';
import DataTable from '../components/DataTable';
import DateRange from '../components/DateRange';
import KpiCard from '../components/KpiCard';
import ManageTable from '../components/ManageTable';
import { Async, PageHead, Tabs } from '../components/UI';
import { useAuth } from '../contexts/AuthContext';
import useFetch from '../hooks/useFetch';
import useFormat from '../hooks/useFormat';
import { iso, makeRange } from '../utils/dates';

function Overview() {
  const f = useFormat(); const [range, setRange] = useState(makeRange('12m'));
  const { data, loading, error, reload } = useFetch('/analytics/expenses', { start: range.start, end: range.end });
  const s = data?.summary;
  return (
    <>
      <div style={{ marginBottom: 16 }}><DateRange value={range} onChange={setRange} presets={['90d', '12m', 'ytd', 'all', 'custom']} /></div>
      <Async loading={loading && !data} error={error} onRetry={reload} rows={7}>
        {data && (<>
          <div className="grid g-4">
            <KpiCard label="Revenue" value={f.money(s.revenue)} /><KpiCard label="Cost of goods" value={f.money(s.cogs)} />
            <KpiCard label="Operating expenses" value={f.money(s.expenses)} /><KpiCard hero label="Net profit" value={f.money(s.profit)} hint={s.margin == null ? undefined : `${s.margin}% margin`} />
          </div>
          <div className="grid g-main">
            <div className="card"><div className="card-head"><h2>Profit and loss by month</h2></div>
              {data.monthly.length ? <TrendChart data={data.monthly} type="composed" series={[{ key: 'revenue', name: 'Revenue', as: 'bar' }, { key: 'expenses', name: 'Expenses', as: 'bar', color: '#d9576b' }, { key: 'profit', name: 'Net profit', color: '#e8a317' }]} /> : <p className="muted">No data in this range.</p>}</div>
            <div className="card"><div className="card-head"><h2>Where the money goes</h2></div>{data.by_category.length ? <Donut data={data.by_category} label="category" value="amount" /> : <p className="muted">No expenses recorded.</p>}</div>
          </div>
          <div className="card"><div className="card-head"><h2>Monthly profit and loss</h2></div>
            <DataTable rows={[...data.monthly].reverse()} rowKey="period" columns={[{ key: 'period', label: 'Month' },
              { key: 'revenue', label: 'Revenue', align: 'right', render: (r) => f.money(r.revenue) }, { key: 'cogs', label: 'Cost of goods', align: 'right', render: (r) => f.money(r.cogs) },
              { key: 'expenses', label: 'Expenses', align: 'right', render: (r) => f.money(r.expenses) },
              { key: 'profit', label: 'Net profit', align: 'right', render: (r) => <span className={r.profit < 0 ? 'bad' : 'good'}>{f.money(r.profit)}</span> }]} /></div>
        </>)}
      </Async>
    </>
  );
}

export default function Expenses() {
  const { can } = useAuth(); const f = useFormat(); const [tab, setTab] = useState('overview');
  return (
    <>
      <PageHead title="Expenses" subtitle="Record spending and see its effect on profit." />
      <Tabs value={tab} onChange={setTab} tabs={[['overview', 'Profit and loss'], ['manage', 'Manage expenses']]} />
      {tab === 'overview' ? <Overview /> : (
        <ManageTable endpoint="/expenses" noun="expense" canWrite={can('data.write')} defaultSort="expense_date" searchPlaceholder="Search description, vendor or category"
          filters={[{ key: 'category', label: 'All categories', options: (d) => d?.categories || [] }]}
          columns={[{ key: 'expense_date', label: 'Date', sortable: true, render: (r) => f.date(r.expense_date) }, { key: 'category', label: 'Category', sortable: true },
            { key: 'description', label: 'Description' }, { key: 'vendor', label: 'Vendor' }, { key: 'amount', label: 'Amount', sortable: true, align: 'right', render: (r) => f.money(r.amount) }]}
          fields={[{ key: 'expense_date', label: 'Date', type: 'date', required: true, default: iso(new Date()) },
            { key: 'category', label: 'Category', type: 'select', required: true, default: 'Other', options: (d) => d?.categories || ['Other'] },
            { key: 'amount', label: 'Amount', type: 'number', required: true, min: 0.01 }, { key: 'vendor', label: 'Vendor' }, { key: 'description', label: 'Description' }]} />)}
    </>
  );
}
