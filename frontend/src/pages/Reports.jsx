import { useState } from 'react';
import { FileDown, FileSpreadsheet, Printer } from '../icons';
import api, { download, errMsg, fieldErrors } from '../api/client';
import DataTable from '../components/DataTable';
import ManageTable from '../components/ManageTable';
import { Field, PageHead, Tabs } from '../components/UI';
import { useToast } from '../contexts/ToastContext';
import useFormat from '../hooks/useFormat';
import { presetRange } from '../utils/dates';

const TYPES = [['revenue', 'Revenue report'], ['sales', 'Sales report'], ['customers', 'Customer report'], ['products', 'Product report'], ['expenses', 'Expense report']];

export default function Reports() {
  const toast = useToast(); const f = useFormat();
  const [tab, setTab] = useState('generate'); const [tick, setTick] = useState(0);
  const [form, setForm] = useState({ type: 'revenue', name: '', ...presetRange('30d') });
  const [result, setResult] = useState(null); const [busy, setBusy] = useState(false); const [errors, setErrors] = useState({});
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  const generate = async (e) => {
    e.preventDefault(); setBusy(true); setErrors({});
    try { setResult((await api.post('/reports', form)).data); setTick(tick + 1); toast.success('Report ready'); }
    catch (err) { setErrors(fieldErrors(err)); toast.error(errMsg(err)); } finally { setBusy(false); }
  };
  const exportAs = async (fmt, src = form) => {
    try { await download('/reports/export', { type: src.type, start: src.start, end: src.end, format: fmt }, `report.${fmt}`); toast.success(`${fmt.toUpperCase()} downloaded`); }
    catch (err) { toast.error(err.response?.data instanceof Blob ? 'Export failed' : errMsg(err)); }
  };
  const fmtCell = (v) => (typeof v === 'number' && !Number.isInteger(v) ? f.money(v) : v);

  return (
    <>
      <PageHead title="Reports center" subtitle="Generate a report for any date range, then export or print it." />
      <Tabs value={tab} onChange={setTab} tabs={[['generate', 'Generate'], ['history', 'History']]} />
      {tab === 'generate' ? (<>
        <form className="card no-print" style={{ marginBottom: 16 }} onSubmit={generate}>
          <div className="grid g-4" style={{ marginBottom: 0 }}>
            <Field label="Report type" htmlFor="r-type"><select id="r-type" className="input" value={form.type} onChange={set('type')}>{TYPES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></Field>
            <Field label="From" error={errors.start} htmlFor="r-from"><input id="r-from" className="input" type="date" value={form.start} max={form.end} onChange={set('start')} required /></Field>
            <Field label="To" error={errors.end} htmlFor="r-to"><input id="r-to" className="input" type="date" value={form.end} min={form.start} onChange={set('end')} required /></Field>
            <Field label="Name (optional)" htmlFor="r-name"><input id="r-name" className="input" value={form.name} onChange={set('name')} /></Field>
          </div>
          <div className="toolbar"><button className="btn primary" disabled={busy}>{busy ? 'Generating…' : 'Generate report'}</button>
            {[['7d', 'Last 7 days'], ['30d', 'Last 30 days'], ['ytd', 'Year to date']].map(([id, l]) => <button type="button" key={id} className="btn sm" onClick={() => setForm({ ...form, ...presetRange(id) })}>{l}</button>)}</div>
        </form>
        {result && (
          <div className="card">
            <div className="card-head"><div><h2>{result.name}</h2><span className="small muted">{result.row_count} rows{result.truncated ? ' (preview shows the first 1,000; exports include everything)' : ''}</span></div>
              <div className="toolbar no-print">
                <button className="btn" onClick={() => exportAs('csv')}><FileSpreadsheet size={16} />CSV</button>
                <button className="btn" onClick={() => exportAs('pdf')}><FileDown size={16} />PDF</button>
                <button className="btn" onClick={() => window.print()}><Printer size={16} />Print</button></div></div>
            <DataTable rowKey="__i" rows={result.rows.map((r, i) => ({ __i: i, r }))} emptyTitle="No data in this period" emptyMessage="Try a wider date range."
              columns={result.columns.map((c, i) => ({ key: String(i), label: c, align: typeof result.rows[0]?.[i] === 'number' ? 'right' : 'left', render: (row) => fmtCell(row.r[i]) }))} dense />
          </div>)}
      </>) : (
        <ManageTable key={tick} endpoint="/reports" noun="report" canWrite defaultSort="created_at" readOnly={false} searchPlaceholder="Search reports"
          columns={[{ key: 'name', label: 'Report', sortable: true }, { key: 'type', label: 'Type' }, { key: 'range', label: 'Period', render: (r) => `${f.date(r.start)} – ${f.date(r.end)}` },
            { key: 'row_count', label: 'Rows', align: 'right' }, { key: 'created_at', label: 'Created', sortable: true, render: (r) => f.date(r.created_at) }]}
          extraActions={(r) => <><button className="btn sm" onClick={() => exportAs('csv', r)}>CSV</button><button className="btn sm" onClick={() => exportAs('pdf', r)}>PDF</button></>} />)}
    </>
  );
}
