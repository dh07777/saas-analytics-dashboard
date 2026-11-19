import { useState } from 'react';
import KpiCard from '../components/KpiCard';
import ManageTable from '../components/ManageTable';
import { PageHead, Pill } from '../components/UI';
import useFetch from '../hooks/useFetch';
import useFormat from '../hooks/useFormat';

export default function Transactions() {
  const f = useFormat(); const { data } = useFetch('/transactions', { per_page: 1 });
  return (
    <>
      <PageHead title="Transactions" subtitle="Every payment and refund recorded against orders." />
      {data && (
        <div className="grid g-3">
          <KpiCard label="Sales received" value={f.money(data.totals.sales)} />
          <KpiCard label="Refunded" value={f.money(data.totals.refunds)} />
          <KpiCard hero label="Net" value={f.money(data.totals.net)} />
        </div>)}
      <ManageTable endpoint="/transactions" noun="transaction" defaultSort="created_at" searchPlaceholder="Search order number or method"
        filters={[{ key: 'type', label: 'Sales and refunds', options: [{ value: 'sale', label: 'Sales' }, { value: 'refund', label: 'Refunds' }] },
          { key: 'method', label: 'Any method', options: ['card', 'bank transfer', 'paypal', 'cash'] }]}
        columns={[{ key: 'created_at', label: 'Date', sortable: true, render: (r) => f.date(r.created_at) }, { key: 'reference', label: 'Order', sortable: true },
          { key: 'customer', label: 'Customer' }, { key: 'method', label: 'Method' },
          { key: 'type', label: 'Type', sortable: true, render: (r) => <Pill tone={r.type === 'refund' ? 'bad' : 'good'}>{r.type}</Pill> },
          { key: 'amount', label: 'Amount', sortable: true, align: 'right', render: (r) => (r.type === 'refund' ? '−' : '') + f.money(r.amount) }]} />
    </>
  );
}
