import { useEffect, useState } from 'react';
import { Pencil, Plus, Search, Trash2 } from '../icons';
import api, { errMsg, fieldErrors } from '../api/client';
import { useToast } from '../contexts/ToastContext';
import useFetch from '../hooks/useFetch';
import DataTable from './DataTable';
import { Async, Confirm, Field, Modal } from './UI';

function FieldInput({ f, value, onChange, id }) {
  if (f.type === 'select') {
    return (
      <select id={id} className="input" value={value ?? ''} onChange={(e) => onChange(e.target.value)}>
        {!f.required && <option value="">—</option>}
        {(f.options || []).map((o) => (typeof o === 'object' ? <option key={o.value} value={o.value}>{o.label}</option> : <option key={o} value={o}>{o}</option>))}
      </select>
    );
  }
  if (f.type === 'checkbox') {
    return <label className="check"><input id={id} type="checkbox" checked={!!value} onChange={(e) => onChange(e.target.checked)} />{f.checkLabel || f.label}</label>;
  }
  return <input id={id} className="input" type={f.type || 'text'} value={value ?? ''} step={f.type === 'number' ? f.step || 'any' : undefined}
    min={f.min} autoComplete={f.type === 'password' ? 'new-password' : 'off'} onChange={(e) => onChange(e.target.value)} />;
}

/**
 * Server-driven list with search, sort, pagination and create/edit/delete.
 * fields: [{key,label,type,required,options,createOnly,hint}]
 */
export default function ManageTable({
  endpoint, columns, fields = [], canWrite, filters = [], defaultSort, defaultOrder = 'desc', noun = 'record',
  searchPlaceholder = 'Search…', extraActions, onChanged, readOnly, toForm, dataKey, perPage = 10, params: extraParams, toolbarExtra,
}) {
  const toast = useToast();
  const [q, setQ] = useState(''); const [dq, setDq] = useState('');
  const [sort, setSort] = useState(defaultSort); const [order, setOrder] = useState(defaultOrder);
  const [page, setPage] = useState(1); const [fv, setFv] = useState({});
  const [editing, setEditing] = useState(null); const [form, setForm] = useState({}); const [errors, setErrors] = useState({});
  const [saving, setSaving] = useState(false); const [deleting, setDeleting] = useState(null);

  useEffect(() => { const t = setTimeout(() => { setDq(q); setPage(1); }, 300); return () => clearTimeout(t); }, [q]);
  const { data, loading, error, reload } = useFetch(endpoint, { q: dq, sort, order, page, per_page: perPage, ...fv, ...extraParams });

  const resolve = (f) => (typeof f.options === 'function' ? { ...f, options: f.options(data) } : f);
  const openNew = () => { setForm(Object.fromEntries(fields.map((f) => [f.key, f.default ?? (f.type === 'checkbox' ? true : '')]))); setErrors({}); setEditing('new'); };
  const openEdit = (row) => { setForm(toForm ? toForm(row) : Object.fromEntries(fields.map((f) => [f.key, row[f.key] ?? '']))); setErrors({}); setEditing(row); };

  const save = async () => {
    setSaving(true); setErrors({});
    const body = {};
    fields.forEach((f) => {
      if (editing !== 'new' && f.createOnly) return;
      const v = form[f.key];
      if (editing !== 'new' && f.type === 'password' && !v) return;
      body[f.key] = f.type === 'number' || f.asNumber ? (v === '' || v == null ? null : Number(v)) : v === '' ? null : v;
    });
    try {
      if (editing === 'new') await api.post(endpoint, body); else await api.put(`${endpoint}/${editing.id}`, body);
      toast.success(`${noun[0].toUpperCase() + noun.slice(1)} ${editing === 'new' ? 'created' : 'saved'}`);
      setEditing(null); reload(); onChanged?.();
    } catch (e) { setErrors(fieldErrors(e)); toast.error(errMsg(e)); } finally { setSaving(false); }
  };

  const remove = async () => {
    setSaving(true);
    try {
      const r = await api.delete(`${endpoint}/${deleting.id}`);
      toast.success(r.data?.message || `${noun} deleted`); setDeleting(null); reload(); onChanged?.();
    } catch (e) { toast.error(errMsg(e)); setDeleting(null); } finally { setSaving(false); }
  };

  const cols = [...columns];
  if (canWrite || extraActions) {
    cols.push({ key: '_actions', label: '', align: 'right', render: (r) => (
      <div className="toolbar no-print" style={{ justifyContent: 'flex-end', flexWrap: 'nowrap' }}>
        {extraActions?.(r)}
        {canWrite && !readOnly && fields.length > 0 && <button className="icon-btn" aria-label={`Edit ${noun}`} onClick={() => openEdit(r)}><Pencil size={16} /></button>}
        {canWrite && !readOnly && <button className="icon-btn" aria-label={`Delete ${noun}`} onClick={() => setDeleting(r)}><Trash2 size={16} /></button>}
      </div>) });
  }
  const rows = dataKey ? data?.[dataKey] : data?.items;

  return (
    <div className="card">
      <div className="toolbar no-print" style={{ marginBottom: 14 }}>
        <div style={{ position: 'relative', flex: '1 1 220px', maxWidth: 340 }}>
          <Search size={16} style={{ position: 'absolute', left: 10, top: 11, color: 'var(--muted)' }} />
          <input className="input" style={{ paddingLeft: 32 }} placeholder={searchPlaceholder} aria-label="Search" value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
        {filters.map((f) => {
          const opts = typeof f.options === 'function' ? f.options(data) : f.options;
          return (
            <select key={f.key} className="input" style={{ width: 'auto' }} aria-label={f.label} value={fv[f.key] ?? ''}
              onChange={(e) => { setFv({ ...fv, [f.key]: e.target.value }); setPage(1); }}>
              <option value="">{f.label}</option>
              {(opts || []).map((o) => (typeof o === 'object' ? <option key={o.value} value={o.value}>{o.label}</option> : <option key={o} value={o}>{o}</option>))}
            </select>);
        })}
        <div style={{ flex: 1 }} />
        {toolbarExtra}
        {canWrite && !readOnly && fields.length > 0 && <button className="btn primary" onClick={openNew}><Plus size={16} />New {noun}</button>}
      </div>
      <Async loading={loading && !data} error={error} onRetry={reload} rows={6}>
        <div style={{ opacity: loading ? 0.6 : 1 }}>
          <DataTable columns={cols} rows={rows} sort={sort} order={order} page={data?.page} pages={data?.pages} total={data?.total}
            onSort={(k) => { if (k === sort) setOrder(order === 'asc' ? 'desc' : 'asc'); else { setSort(k); setOrder('asc'); } setPage(1); }}
            onPage={setPage} emptyTitle={dq ? 'No matches' : `No ${noun}s yet`}
            emptyMessage={dq ? 'Try a different search term.' : canWrite ? `Add your first ${noun} to get started.` : undefined} />
        </div>
      </Async>

      {editing && (
        <Modal title={`${editing === 'new' ? 'New' : 'Edit'} ${noun}`} onClose={() => setEditing(null)}
          footer={<><button className="btn" onClick={() => setEditing(null)}>Cancel</button><button className="btn primary" disabled={saving} onClick={save}>{saving ? 'Saving…' : 'Save changes'}</button></>}>
          {fields.filter((f) => editing === 'new' || !f.createOnly).map((raw) => {
            const f = resolve(raw);
            return (
              <Field key={f.key} label={f.type === 'checkbox' ? null : f.label + (f.required ? ' *' : '')} error={errors[f.key]} hint={f.hint} htmlFor={`f-${f.key}`}>
                <FieldInput f={f} id={`f-${f.key}`} value={form[f.key]} onChange={(v) => setForm({ ...form, [f.key]: v })} />
              </Field>);
          })}
        </Modal>
      )}
      {deleting && <Confirm title={`Delete ${noun}?`} message="This cannot be undone." busy={saving} onConfirm={remove} onClose={() => setDeleting(null)} />}
    </div>
  );
}
