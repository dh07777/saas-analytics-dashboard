import { useState } from 'react';
import DataTable from '../components/DataTable';
import DateRange from '../components/DateRange';
import KpiCard from '../components/KpiCard';
import ManageTable from '../components/ManageTable';
import { BarList } from '../components/charts';
import { Async, PageHead, Pill, Tabs } from '../components/UI';
import { useAuth } from '../contexts/AuthContext';
import useFetch from '../hooks/useFetch';
import useFormat from '../hooks/useFormat';
import { makeRange } from '../utils/dates';

function Analytics() {
  const f = useFormat(); const [range, setRange] = useState(makeRange('90d'));
  const { data, loading, error, reload } = useFetch('/analytics/products', { start: range.start, end: range.end });
  const k = data?.kpis;
  const prodCols = [{ key: 'name', label: 'Product' }, { key: 'category', label: 'Category' },
    { key: 'units', label: 'Units', align: 'right' }, { key: 'revenue', label: 'Revenue', align: 'right', render: (r) => f.money(r.revenue) },
    { key: 'margin_pct', label: 'Margin', align: 'right', render: (r) => (r.margin_pct == null ? '—' : `${r.margin_pct.toFixed(0)}%`) }];
  return (
    <>
      <div style={{ marginBottom: 16 }}><DateRange value={range} onChange={setRange} presets={['30d', '90d', '12m', 'ytd', 'custom']} /></div>
      <Async loading={loading && !data} error={error} onRetry={reload} rows={7} empty={data && !data.inventory.length} emptyProps={{ title: 'No products yet', message: 'Add products in the Manage tab.' }}>
        {data && (<>
          <div className="grid g-4">
            <KpiCard label="Active products" value={f.num(k.active_products)} />
            <KpiCard label="Stock value (at cost)" value={f.money(k.stock_value)} hint={`${f.money(k.retail_value)} at retail`} />
            <KpiCard label="Low stock" value={f.num(k.low_stock)} hint={`${k.out_of_stock} out of stock`} />
            <KpiCard label="Overstocked" value={f.num(k.overstocked)} hint="More than 180 days of cover" />
          </div>
          <div className="grid g-2">
            <div className="card"><div className="card-head"><h2>Best sellers</h2></div><BarList data={data.best_sellers.slice(0, 8)} label="name" value="revenue" /></div>
            <div className="card"><div className="card-head"><h2>Category performance</h2></div><BarList data={data.category_performance} label="category" value="revenue" /></div>
          </div>
          <div className="grid g-2">
            <div className="card"><div className="card-head"><h2>Low performers</h2></div><DataTable dense rowKey="product_id" rows={data.low_performers} columns={prodCols} /></div>
            <div className="card"><div className="card-head"><h2>Needs restocking</h2></div>
              <DataTable dense rowKey="product_id" rows={data.low_stock_items} emptyTitle="Stock looks healthy" emptyMessage="No product is at or below its reorder level." columns={[
                { key: 'name', label: 'Product' }, { key: 'stock', label: 'In stock', align: 'right', render: (r) => <Pill tone={r.stock <= 0 ? 'bad' : 'warn'}>{r.stock}</Pill> },
                { key: 'reorder_level', label: 'Reorder at', align: 'right' }, { key: 'days_of_cover', label: 'Days left', align: 'right', render: (r) => (r.days_of_cover == null ? '—' : Math.round(r.days_of_cover)) }]} /></div>
          </div>
        </>)}
      </Async>
    </>
  );
}

export default function Products() {
  const { can } = useAuth(); const f = useFormat(); const [tab, setTab] = useState('analytics');
  const { data: cats, reload } = useFetch('/categories', { all: 1 });
  const catOptions = (cats?.items || []).map((c) => ({ value: c.id, label: c.name }));
  return (
    <>
      <PageHead title="Products" subtitle="Performance, inventory and the product catalogue." />
      <Tabs value={tab} onChange={setTab} tabs={[['analytics', 'Analytics'], ['manage', 'Manage products'], ['categories', 'Categories']]} />
      {tab === 'analytics' && <Analytics />}
      {tab === 'manage' && (
        <ManageTable endpoint="/products" noun="product" canWrite={can('data.write')} defaultSort="name" defaultOrder="asc" searchPlaceholder="Search name or SKU"
          filters={[{ key: 'category_id', label: 'All categories', options: catOptions }, { key: 'low_stock', label: 'All stock levels', options: [{ value: '1', label: 'Low stock only' }] }]}
          columns={[{ key: 'name', label: 'Product', sortable: true }, { key: 'sku', label: 'SKU', sortable: true }, { key: 'category', label: 'Category' },
            { key: 'price', label: 'Price', sortable: true, align: 'right', render: (r) => f.money(r.price) },
            { key: 'stock', label: 'Stock', sortable: true, align: 'right', render: (r) => <Pill tone={r.stock <= 0 ? 'bad' : r.low_stock ? 'warn' : 'good'}>{r.stock}</Pill> },
            { key: 'is_active', label: 'Status', render: (r) => (r.is_active ? 'Active' : 'Inactive') }]}
          fields={[{ key: 'name', label: 'Name', required: true }, { key: 'sku', label: 'SKU', required: true }, { key: 'category_id', label: 'Category', type: 'select', options: catOptions, asNumber: true },
            { key: 'price', label: 'Price', type: 'number', required: true, min: 0 }, { key: 'cost', label: 'Unit cost', type: 'number', min: 0, default: 0 },
            { key: 'stock', label: 'Stock', type: 'number', step: 1, min: 0, default: 0 }, { key: 'reorder_level', label: 'Reorder level', type: 'number', step: 1, min: 0, default: 10 },
            { key: 'is_active', label: 'Active', type: 'checkbox', checkLabel: 'Active (available for sale)' }]} />)}
      {tab === 'categories' && (
        <ManageTable endpoint="/categories" noun="category" canWrite={can('data.write')} defaultSort="name" defaultOrder="asc" onChanged={reload}
          columns={[{ key: 'name', label: 'Category', sortable: true }, { key: 'products', label: 'Products', align: 'right' }]}
          fields={[{ key: 'name', label: 'Name', required: true }]} />)}
    </>
  );
}
