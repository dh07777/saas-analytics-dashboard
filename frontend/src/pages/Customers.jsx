import { useState } from 'react';
import { BarChart, Bar, CartesianGrid, Legend, Line, ComposedChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import DataTable from '../components/DataTable';
import DateRange from '../components/DateRange';
import KpiCard from '../components/KpiCard';
import ManageTable from '../components/ManageTable';
import { Donut } from '../components/charts';
import { Async, PageHead, Pill, Tabs } from '../components/UI';
import { useAuth } from '../contexts/AuthContext';
import useFetch from '../hooks/useFetch';
import useFormat from '../hooks/useFormat';
import { makeRange } from '../utils/dates';

const SEG_TONE = { VIP: 'info', New: 'good', Active: 'good', 'At risk': 'warn', Lost: 'bad' };

function Analytics() {
  const f = useFormat(); const [range, setRange] = useState(makeRange('90d'));
  const { data, loading, error, reload } = useFetch('/analytics/customers', { start: range.start, end: range.end });
  const ltv = data?.lifetime_value;
  return (
    <>
      <div style={{ marginBottom: 16 }}><DateRange value={range} onChange={setRange} presets={['30d', '90d', '12m', 'ytd', 'custom']} /></div>
      <Async loading={loading && !data} error={error} onRetry={reload} rows={7}>
        {data && (<>
          <div className="grid g-4">
            <KpiCard label="Total customers" value={f.num(data.total_customers)} hint={`${data.registered_in_period} signed up in period`} />
            <KpiCard label="New buyers" value={f.num(data.new_customers)} hint="First purchase in period" />
            <KpiCard label="Returning buyers" value={f.num(data.returning_customers)} hint="Bought before this period" />
            <KpiCard label="Retention" value={data.retention_rate == null ? '—' : `${data.retention_rate}%`} hint="Previous-period buyers who bought again" />
          </div>
          <div className="grid g-main">
            <div className="card"><div className="card-head"><h2>Customer growth</h2></div>
              {data.growth.length ? (
                <div className="chart" role="img" aria-label="Customer growth chart"><ResponsiveContainer>
                  <ComposedChart data={data.growth}><CartesianGrid vertical={false} /><XAxis dataKey="period" tick={{ fill: 'currentColor', fontSize: 12 }} /><YAxis tick={{ fill: 'currentColor', fontSize: 12 }} width={40} />
                    <Tooltip /><Legend /><Bar dataKey="new" name="New customers" fill="#167a8e" radius={[3, 3, 0, 0]} /><Line dataKey="total" name="Total customers" stroke="#e8a317" strokeWidth={2.5} dot={false} /></ComposedChart>
                </ResponsiveContainer></div>) : <p className="muted">No customers yet.</p>}
            </div>
            <div className="card"><div className="card-head"><h2>Segments</h2></div>
              {data.segments.length ? <Donut data={data.segments} label="segment" value="customers" money={false} /> : <p className="muted">Segments appear once customers place orders.</p>}</div>
          </div>
          {ltv && (
            <div className="grid g-4">
              <KpiCard label="Lifetime value" value={f.money(ltv.avg_lifetime_value)} hint="Average gross profit per buyer" />
              <KpiCard label="Revenue per customer" value={f.money(ltv.avg_revenue_per_customer)} />
              <KpiCard label="Orders per customer" value={ltv.avg_orders_per_customer} />
              <KpiCard label="Average order" value={f.money(ltv.avg_order_value)} />
            </div>)}
          <div className="card"><div className="card-head"><h2>Top customers</h2></div>
            <DataTable rows={data.top_customers} rowKey="customer_id" emptyTitle="No buyers yet" columns={[
              { key: 'name', label: 'Customer' }, { key: 'segment', label: 'Segment', render: (r) => <Pill tone={SEG_TONE[r.segment]}>{r.segment}</Pill> },
              { key: 'orders', label: 'Orders', align: 'right' }, { key: 'revenue', label: 'Revenue', align: 'right', render: (r) => f.money(r.revenue) },
              { key: 'lifetime_value', label: 'Lifetime value', align: 'right', render: (r) => f.money(r.lifetime_value) }, { key: 'last_order', label: 'Last order', render: (r) => f.date(r.last_order) }]} /></div>
        </>)}
      </Async>
    </>
  );
}

export default function Customers() {
  const { can } = useAuth(); const f = useFormat(); const [tab, setTab] = useState('analytics');
  return (
    <>
      <PageHead title="Customers" subtitle="Who buys, who comes back, and who is slipping away." />
      <Tabs value={tab} onChange={setTab} tabs={[['analytics', 'Analytics'], ['manage', 'Manage customers']]} />
      {tab === 'analytics' ? <Analytics /> : (
        <ManageTable endpoint="/customers" noun="customer" canWrite={can('data.write')} defaultSort="created_at" searchPlaceholder="Search name, email or phone"
          filters={[{ key: 'region', label: 'All regions', options: (d) => d?.regions || [] }]}
          columns={[{ key: 'name', label: 'Name', sortable: true }, { key: 'email', label: 'Email' }, { key: 'region', label: 'Region', sortable: true },
            { key: 'orders', label: 'Orders', align: 'right' }, { key: 'total_spent', label: 'Spent', align: 'right', render: (r) => f.money(r.total_spent) },
            { key: 'created_at', label: 'Joined', sortable: true, render: (r) => f.date(r.created_at) }]}
          fields={[{ key: 'name', label: 'Name', required: true }, { key: 'email', label: 'Email', type: 'email' }, { key: 'phone', label: 'Phone' },
            { key: 'region', label: 'Region', type: 'select', options: (d) => d?.regions || [] }]} />)}
    </>
  );
}
