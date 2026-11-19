import { useState } from 'react';
import { Eye, Plus, Trash2 } from '../icons';
import api, { errMsg } from '../api/client';
import { BarList, Donut, TrendChart } from '../components/charts';
import DataTable from '../components/DataTable';
import DateRange from '../components/DateRange';
import KpiCard from '../components/KpiCard';
import ManageTable from '../components/ManageTable';
import { Async, Delta, Field, Modal, PageHead, Pill, Tabs } from '../components/UI';
import { useAuth } from '../contexts/AuthContext';
import { useToast } from '../contexts/ToastContext';
import useFetch from '../hooks/useFetch';
import useFormat from '../hooks/useFormat';
import { makeRange } from '../utils/dates';

const TONE = { completed: 'good', pending: 'warn', cancelled: 'bad', refunded: 'bad' };

function Analytics() {
  const f = useFormat(); const [range, setRange] = useState(makeRange('90d'));
  const { data, loading, error, reload } = useFetch('/analytics/sales', { start: range.start, end: range.end });
  const t = data?.totals;
  return (
    <>
      <div style={{ marginBottom: 16 }}><DateRange value={range} onChange={setRange} presets={['30d', '90d', '12m', 'ytd', 'custom']} /></div>
      <Async loading={loading && !data} error={error} onRetry={reload} rows={7} empty={data && !data.by_category.length}
        emptyProps={{ title: 'No sales in this period', message: 'Pick a longer range or record an order in the Orders tab.' }}>
        {data && (<>
          <div className="grid g-4">
            <KpiCard hero label="Total sales" value={f.money(t.sales)} change={t.change_pct} hint="vs previous period" />
            <KpiCard label="Orders" value={f.num(t.orders)} /><KpiCard label="Units sold" value={f.num(t.units)} /><KpiCard label="Average order" value={f.money(t.aov)} />
          </div>
          <div className="card" style={{ marginBottom: 16 }}><div className="card-head"><h2>Sales trend</h2></div><TrendChart data={data.trend} series={[{ key: 'revenue', name: 'Revenue' }]} /></div>
          <div className="grid g-3">
            <div className="card"><div className="card-head"><h2>By category</h2></div><Donut data={data.by_category} label="category" value="revenue" /></div>
            <div className="card"><div className="card-head"><h2>By region</h2></div><BarList data={data.by_region} label="region" value="revenue" /></div>
            <div className="card"><div className="card-head"><h2>Top products</h2></div><BarList data={data.by_product.slice(0, 6)} label="product" value="revenue" /></div>
          </div>
          <div className="card"><div className="card-head"><h2>Category performance vs previous period</h2></div>
            <DataTable rows={data.comparison} rowKey="category" columns={[{ key: 'category', label: 'Category' },
              { key: 'current', label: 'This period', align: 'right', render: (r) => f.money(r.current) },
              { key: 'previous', label: 'Previous', align: 'right', render: (r) => f.money(r.previous) },
              { key: 'change_pct', label: 'Change', align: 'right', render: (r) => <Delta value={r.change_pct} /> }]} /></div>
        </>)}
      </Async>
    </>
  );
}

function NewOrder({ onClose, onSaved }) {
  const toast = useToast(); const f = useFormat();
  const { data: prods } = useFetch('/products', { per_page: 100, active: 1, sort: 'name', order: 'asc' });
  const { data: custs } = useFetch('/customers', { per_page: 100, sort: 'name', order: 'asc' });
  const [lines, setLines] = useState([{ product_id: '', quantity: 1 }]); const [customer, setCustomer] = useState('');
  const [region, setRegion] = useState(''); const [status, setStatus] = useState('completed'); const [method, setMethod] = useState('card');
  const [busy, setBusy] = useState(false); const [error, setError] = useState('');
  const price = (id) => prods?.items.find((p) => p.id === Number(id))?.price || 0;
  const total = lines.reduce((s, l) => s + price(l.product_id) * (Number(l.quantity) || 0), 0);
  const upd = (i, k, v) => setLines(lines.map((l, j) => (j === i ? { ...l, [k]: v } : l)));
  const save = async () => {
    setBusy(true); setError('');
    try {
      await api.post('/orders', { customer_id: customer ? Number(customer) : null, region: region || null, status, method,
        items: lines.filter((l) => l.product_id).map((l) => ({ product_id: Number(l.product_id), quantity: Number(l.quantity) })) });
      toast.success('Order recorded'); onSaved(); onClose();
    } catch (e) { setError(errMsg(e)); } finally { setBusy(false); }
  };
  return (
    <Modal title="New order" onClose={onClose} width={640} footer={<><button className="btn" onClick={onClose}>Cancel</button><button className="btn primary" disabled={busy || !lines.some((l) => l.product_id)} onClick={save}>{busy ? 'Saving…' : `Record order · ${f.money(total)}`}</button></>}>
      <div className="grid g-2" style={{ marginBottom: 0 }}>
        <Field label="Customer" htmlFor="o-c"><select id="o-c" className="input" value={customer} onChange={(e) => setCustomer(e.target.value)}><option value="">Walk-in customer</option>{custs?.items.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</select></Field>
        <Field label="Region" htmlFor="o-r"><select id="o-r" className="input" value={region} onChange={(e) => setRegion(e.target.value)}><option value="">—</option>{custs?.regions.map((r) => <option key={r}>{r}</option>)}</select></Field>
        <Field label="Status" htmlFor="o-s"><select id="o-s" className="input" value={status} onChange={(e) => setStatus(e.target.value)}><option value="completed">Completed</option><option value="pending">Pending</option></select></Field>
        <Field label="Payment method" htmlFor="o-m"><select id="o-m" className="input" value={method} onChange={(e) => setMethod(e.target.value)}>{['card', 'bank transfer', 'paypal', 'cash'].map((m) => <option key={m}>{m}</option>)}</select></Field>
      </div>
      <h3 style={{ margin: '4px 0 10px' }}>Items</h3>
      {lines.map((l, i) => (
        <div key={i} style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
          <select className="input" aria-label={`Product ${i + 1}`} value={l.product_id} onChange={(e) => upd(i, 'product_id', e.target.value)}>
            <option value="">Choose a product</option>{prods?.items.map((p) => <option key={p.id} value={p.id} disabled={p.stock < 1}>{p.name} · {f.money(p.price)} · {p.stock} in stock</option>)}</select>
          <input className="input" type="number" min="1" aria-label={`Quantity ${i + 1}`} style={{ width: 80 }} value={l.quantity} onChange={(e) => upd(i, 'quantity', e.target.value)} />
          <button className="icon-btn" aria-label="Remove item" disabled={lines.length === 1} onClick={() => setLines(lines.filter((_, j) => j !== i))}><Trash2 size={16} /></button>
        </div>))}
      <button className="btn sm" onClick={() => setLines([...lines, { product_id: '', quantity: 1 }])}><Plus size={14} />Add item</button>
      {error && <p role="alert" className="bad">{error}</p>}
    </Modal>
  );
}

function OrderDetail({ id, onClose }) {
  const f = useFormat(); const { data, loading, error, reload } = useFetch(`/orders/${id}`);
  return (
    <Modal title={data ? `Order ${data.order_number}` : 'Order'} onClose={onClose} width={620}>
      <Async loading={loading} error={error} onRetry={reload}>
        {data && (<>
          <div className="grid g-2" style={{ marginBottom: 12 }}>
            <div><div className="small muted">Customer</div>{data.customer}</div><div><div className="small muted">Date</div>{f.dateTime(data.order_date)}</div>
            <div><div className="small muted">Region</div>{data.region || '—'}</div><div><div className="small muted">Status</div><Pill tone={TONE[data.status]}>{data.status}</Pill></div>
          </div>
          <DataTable dense rowKey="product_id" rows={data.items} columns={[{ key: 'product', label: 'Product' }, { key: 'quantity', label: 'Qty', align: 'right' },
            { key: 'unit_price', label: 'Unit price', align: 'right', render: (r) => f.money(r.unit_price) }, { key: 'line', label: 'Line total', align: 'right', render: (r) => f.money(r.unit_price * r.quantity) }]} />
          <p className="right" style={{ marginBottom: 0 }}><strong>Total {f.money(data.total)}</strong></p>
        </>)}
      </Async>
    </Modal>
  );
}

function Orders() {
  const { can } = useAuth(); const f = useFormat(); const toast = useToast();
  const [adding, setAdding] = useState(false); const [tick, setTick] = useState(0); const [viewing, setViewing] = useState(null);
  const act = async (o, status) => {
    try { await api.patch(`/orders/${o.id}`, { status }); toast.success(`Order ${status}`); setTick(tick + 1); } catch (e) { toast.error(errMsg(e)); }
  };
  return (
    <>
      <ManageTable key={tick} endpoint="/orders" noun="order" canWrite={can('data.write')} defaultSort="order_date" searchPlaceholder="Search order number or customer"
        filters={[{ key: 'status', label: 'All statuses', options: ['completed', 'pending', 'cancelled', 'refunded'] }]}
        toolbarExtra={can('data.write') && <button className="btn primary" onClick={() => setAdding(true)}><Plus size={16} />New order</button>}
        columns={[{ key: 'order_number', label: 'Order', sortable: true }, { key: 'customer', label: 'Customer' },
          { key: 'order_date', label: 'Date', sortable: true, render: (r) => f.date(r.order_date) }, { key: 'item_count', label: 'Items', align: 'right' },
          { key: 'status', label: 'Status', sortable: true, render: (r) => <Pill tone={TONE[r.status]}>{r.status}</Pill> },
          { key: 'total', label: 'Total', sortable: true, align: 'right', render: (r) => f.money(r.total) }]}
        extraActions={(r) => (<>
          <button className="icon-btn" aria-label="View order" onClick={() => setViewing(r.id)}><Eye size={16} /></button>
          {can('data.write') && (<>
          {r.status === 'pending' && <button className="btn sm" onClick={() => act(r, 'completed')}>Complete</button>}
          {r.status === 'pending' && <button className="btn sm" onClick={() => act(r, 'cancelled')}>Cancel</button>}
          {r.status === 'completed' && <button className="btn sm" onClick={() => act(r, 'refunded')}>Refund</button>}</>)}</>)} />
      {viewing && <OrderDetail id={viewing} onClose={() => setViewing(null)} />}
      {adding && <NewOrder onClose={() => setAdding(false)} onSaved={() => setTick(tick + 1)} />}
    </>
  );
}

export default function Sales() {
  const [tab, setTab] = useState('analytics');
  return (
    <>
      <PageHead title="Sales" subtitle="What sold, where, and how it compares with the previous period." />
      <Tabs value={tab} onChange={setTab} tabs={[['analytics', 'Analytics'], ['orders', 'Orders']]} />
      {tab === 'analytics' ? <Analytics /> : <Orders />}
    </>
  );
}
