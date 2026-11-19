import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Activity, DollarSign, Settings2, ShoppingCart, TrendingUp, Users, Wallet } from '../icons';
import api, { errMsg } from '../api/client';
import { BarList, Donut, TrendChart } from '../components/charts';
import DataTable from '../components/DataTable';
import DateRange from '../components/DateRange';
import KpiCard from '../components/KpiCard';
import { Async, Modal, PageHead, Pill } from '../components/UI';
import { useAuth } from '../contexts/AuthContext';
import { useToast } from '../contexts/ToastContext';
import useFetch from '../hooks/useFetch';
import useFormat from '../hooks/useFormat';
import { makeRange } from '../utils/dates';

const WIDGETS = [['trend', 'Revenue & profit trend'], ['categories', 'Sales by category'], ['topProducts', 'Top products'], ['transactions', 'Recent transactions'], ['activity', 'Recent activity']];

export default function Dashboard() {
  const { user, setUser } = useAuth(); const toast = useToast(); const f = useFormat();
  const [range, setRange] = useState(makeRange('30d')); const [custom, setCustom] = useState(false);
  const [widgets, setWidgets] = useState(user.settings.dashboard_widgets);
  useEffect(() => setWidgets(user.settings.dashboard_widgets), [user.settings.dashboard_widgets]);
  const { data, loading, error, reload } = useFetch('/analytics/dashboard', { start: range.start, end: range.end });
  const on = (w) => widgets.includes(w);
  const k = data?.kpis;

  const saveWidgets = async () => {
    try {
      const r = await api.put('/settings/user', { dashboard_widgets: widgets });
      setUser({ ...user, settings: r.data.user }); setCustom(false); toast.success('Dashboard updated');
    } catch (e) { toast.error(errMsg(e)); }
  };

  return (
    <>
      <PageHead title={`Hello, ${user.full_name.split(' ')[0]}`} subtitle="Here's how the business is doing in the selected period.">
        <DateRange value={range} onChange={setRange} presets={['7d', '30d', '90d', '12m', 'ytd', 'custom']} />
        <button className="btn" onClick={() => setCustom(true)}><Settings2 size={16} />Customize</button>
      </PageHead>
      <Async loading={loading && !data} error={error} onRetry={reload} rows={8}>
        {data && (<>
          <div className="grid g-main">
            <KpiCard hero label="Total revenue" icon={DollarSign} value={f.money(k.revenue)} change={k.revenue_growth} hint={`vs previous ${((new Date(range.end) - new Date(range.start)) / 864e5 + 1) | 0} days`} />
            <div className="card kpi"><div className="kpi-label"><TrendingUp size={16} />Monthly growth</div>
              <div className="kpi-value">{k.monthly_growth == null ? '—' : `${k.monthly_growth > 0 ? '+' : ''}${k.monthly_growth}%`}</div>
              <div className="small muted">Last full month vs the one before</div></div>
          </div>
          <div className="grid g-4">
            <KpiCard label="Net profit" icon={Wallet} value={f.money(k.profit)} change={k.profit_growth} hint={k.margin == null ? undefined : `${k.margin}% margin`} />
            <KpiCard label="Orders" icon={ShoppingCart} value={f.num(k.orders)} change={k.orders_growth} hint={`Avg order ${f.money(k.aov)}`} />
            <KpiCard label="Customers" icon={Users} value={f.num(k.total_customers)} change={k.customers_growth} hint={`${k.new_customers} new in period`} />
            <KpiCard label="Expenses" icon={Activity} value={f.money(k.expenses)} hint={`Gross profit ${f.money(k.gross_profit)}`} />
          </div>
          {on('trend') && (
            <div className="card" style={{ marginBottom: 16 }}>
              <div className="card-head"><h2>Revenue and profit</h2><Link to="/revenue" className="small">Open revenue analytics</Link></div>
              {data.trend.length ? <TrendChart data={data.trend} type="composed" series={[{ key: 'revenue', name: 'Revenue', as: 'bar' }, { key: 'profit', name: 'Net profit', color: '#e8a317' }]} />
                : <p className="muted">No completed orders in this period.</p>}
            </div>)}
          <div className="grid g-2">
            {on('categories') && <div className="card"><div className="card-head"><h2>Sales by category</h2></div>{data.by_category.length ? <Donut data={data.by_category} label="category" value="revenue" /> : <p className="muted">No sales yet.</p>}</div>}
            {on('topProducts') && <div className="card"><div className="card-head"><h2>Top products</h2></div>{data.top_products.length ? <BarList data={data.top_products} label="product" value="revenue" /> : <p className="muted">No sales yet.</p>}</div>}
          </div>
          <div className="grid g-main">
            {on('transactions') && (
              <div className="card"><div className="card-head"><h2>Recent transactions</h2></div>
                <DataTable dense rows={data.recent_transactions} emptyTitle="No transactions yet" columns={[
                  { key: 'reference', label: 'Order' }, { key: 'customer', label: 'Customer' },
                  { key: 'type', label: 'Type', render: (r) => <Pill tone={r.type === 'refund' ? 'bad' : 'good'}>{r.type}</Pill> },
                  { key: 'amount', label: 'Amount', align: 'right', render: (r) => (r.type === 'refund' ? '−' : '') + f.money(r.amount) },
                  { key: 'created_at', label: 'Date', render: (r) => f.date(r.created_at) }]} /></div>)}
            {on('activity') && (
              <div className="card"><div className="card-head"><h2>Recent activity</h2></div>
                {data.recent_activities.length ? data.recent_activities.map((a) => (
                  <div key={a.id} className="list-row"><div style={{ flex: 1 }}><strong>{a.user}</strong> <span className="muted">{a.action} {a.entity || ''}</span>
                    {a.details && <div className="small muted">{a.details}</div>}</div><span className="small muted nowrap">{f.date(a.created_at)}</span></div>)) : <p className="muted">No activity yet.</p>}
              </div>)}
          </div>
        </>)}
      </Async>
      {custom && (
        <Modal title="Customize dashboard" onClose={() => setCustom(false)} footer={<><button className="btn" onClick={() => setCustom(false)}>Cancel</button><button className="btn primary" onClick={saveWidgets}>Save changes</button></>}>
          <p className="muted" style={{ marginTop: 0 }}>Choose which sections appear. The KPI cards are always shown.</p>
          {WIDGETS.map(([id, label]) => (
            <label key={id} className="check field"><input type="checkbox" checked={widgets.includes(id)} onChange={(e) => setWidgets(e.target.checked ? [...widgets, id] : widgets.filter((w) => w !== id))} />{label}</label>))}
        </Modal>)}
    </>
  );
}
