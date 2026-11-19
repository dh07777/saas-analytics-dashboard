import { useEffect, useState } from 'react';
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import api, { errMsg } from '../api/client';
import DataTable from '../components/DataTable';
import KpiCard from '../components/KpiCard';
import ManageTable from '../components/ManageTable';
import { Async, Field, PageHead, Pill, Tabs } from '../components/UI';
import { useToast } from '../contexts/ToastContext';
import useFetch from '../hooks/useFetch';
import useFormat from '../hooks/useFormat';

const kb = (n) => (n == null ? 'n/a' : n > 1048576 ? `${(n / 1048576).toFixed(1)} MB` : `${(n / 1024).toFixed(0)} KB`);

function Overview() {
  const f = useFormat(); const o = useFetch('/admin/overview'); const a = useFetch('/admin/activity');
  return (
    <Async loading={o.loading && !o.data} error={o.error} onRetry={o.reload}>
      {o.data && (<>
        <div className="grid g-4">
          <KpiCard label="Businesses" value={o.data.businesses} /><KpiCard label="Users" value={o.data.users} hint={`${o.data.active_users} active`} />
          <KpiCard label="Sign-ins (24h)" value={o.data.logins_24h} hint={`${o.data.failed_logins_24h} failed`} /><KpiCard label="Audit events" value={f.num(o.data.audit_events)} hint={`Environment: ${o.data.environment}`} />
        </div>
        <div className="grid g-main">
          <div className="card"><div className="card-head"><h2>Sign-ins, last 14 days</h2></div>
            {a.data?.logins.length ? <div className="chart sm"><ResponsiveContainer><BarChart data={a.data.logins}><CartesianGrid vertical={false} /><XAxis dataKey="date" tick={{ fill: 'currentColor', fontSize: 11 }} /><YAxis allowDecimals={false} tick={{ fill: 'currentColor', fontSize: 12 }} width={30} /><Tooltip /><Legend />
              <Bar dataKey="login" name="Successful" fill="#167a8e" /><Bar dataKey="login_failed" name="Failed" fill="#d9576b" /></BarChart></ResponsiveContainer></div> : <p className="muted">No sign-ins recorded yet.</p>}</div>
          <div className="card"><div className="card-head"><h2>System activity</h2></div>
            {(a.data?.recent || []).slice(0, 8).map((x) => <div key={x.id} className="list-row"><div style={{ flex: 1 }}><strong>{x.user}</strong> <span className="muted">{x.action} {x.entity || ''}</span></div><span className="small muted">{f.date(x.created_at)}</span></div>)}</div>
        </div>
      </>)}
    </Async>
  );
}

function Database() {
  const { data, loading, error, reload } = useFetch('/admin/db-stats');
  return (
    <Async loading={loading} error={error} onRetry={reload}>
      {data && (<>
        <div className="grid g-3"><KpiCard label="Engine" value={data.engine} /><KpiCard label="File size" value={kb(data.size_bytes)} /><KpiCard label="Total rows" value={data.total_rows.toLocaleString()} /></div>
        <div className="card"><DataTable rowKey="table" rows={data.tables} columns={[{ key: 'table', label: 'Table' }, { key: 'rows', label: 'Rows', align: 'right', render: (r) => r.rows.toLocaleString() }]} /></div>
      </>)}
    </Async>
  );
}

function Roles() {
  const toast = useToast(); const { data, loading, error, reload } = useFetch('/admin/roles');
  const [draft, setDraft] = useState({});
  useEffect(() => { if (data) setDraft(Object.fromEntries(data.roles.map((r) => [r.id, r.permissions]))); }, [data]);
  const toggle = (rid, code) => setDraft({ ...draft, [rid]: draft[rid].includes(code) ? draft[rid].filter((c) => c !== code) : [...draft[rid], code] });
  const save = async (r) => { try { await api.put(`/admin/roles/${r.id}/permissions`, { permissions: draft[r.id] }); toast.success(`${r.label} permissions saved. Users get them on next request.`); reload(); } catch (e) { toast.error(errMsg(e)); } };
  return (
    <Async loading={loading || !data} error={error} onRetry={reload}>
      {data && (
        <div className="card">
          <p className="muted" style={{ marginTop: 0 }}>Tick what each role may do. Changes apply immediately. Super Admin is fixed.</p>
          <div className="table-wrap"><table className="table">
            <thead><tr><th>Permission</th>{data.roles.map((r) => <th key={r.id} style={{ textAlign: 'center' }}>{r.label}<div className="small muted">{r.users} users</div></th>)}</tr></thead>
            <tbody>
              {data.permissions.map((p) => (
                <tr key={p.code}><td><code>{p.code}</code><div className="small muted">{p.description}</div></td>
                  {data.roles.map((r) => (
                    <td key={r.id} style={{ textAlign: 'center' }}>
                      <input type="checkbox" aria-label={`${r.label} ${p.code}`} checked={(draft[r.id] || []).includes(p.code)}
                        disabled={r.locked || p.code === 'admin.access' || p.code === 'dashboard.view'} onChange={() => toggle(r.id, p.code)} />
                    </td>))}</tr>))}
              <tr><td /> {data.roles.map((r) => <td key={r.id} style={{ textAlign: 'center' }}>{!r.locked && <button className="btn sm primary" onClick={() => save(r)}>Save</button>}</td>)}</tr>
            </tbody></table></div>
        </div>)}
    </Async>
  );
}

function Config() {
  const toast = useToast(); const { data, loading, error, reload } = useFetch('/admin/config');
  const [form, setForm] = useState(null);
  useEffect(() => { if (data) setForm(data.editable); }, [data]);
  const save = async () => { try { await api.put('/admin/config', form); toast.success('Configuration saved'); reload(); } catch (e) { toast.error(errMsg(e)); } };
  return (
    <Async loading={loading || !form} error={error} onRetry={reload}>
      {data && form && (
        <div className="grid g-2">
          <div className="card"><h2 style={{ marginBottom: 14 }}>Application settings</h2>
            <label className="check field"><input type="checkbox" checked={form.allow_registration} onChange={(e) => setForm({ ...form, allow_registration: e.target.checked })} />Allow new sign-ups</label>
            <Field label="Announcement banner" hint="Shown to every signed-in user. Leave empty to hide." htmlFor="ann"><input id="ann" className="input" maxLength={300} value={form.announcement} onChange={(e) => setForm({ ...form, announcement: e.target.value })} /></Field>
            <button className="btn primary" onClick={save}>Save changes</button></div>
          <div className="card"><h2 style={{ marginBottom: 14 }}>Server configuration</h2><p className="small muted">Set in the backend .env file. Restart the server to change.</p>
            {Object.entries(data.readonly).map(([k, v]) => <div key={k} className="list-row"><span style={{ flex: 1 }} className="muted">{k.replaceAll('_', ' ')}</span><span>{Array.isArray(v) ? v.join(', ') : String(v)}</span></div>)}</div>
        </div>)}
    </Async>
  );
}

export default function Admin() {
  const f = useFormat(); const [tab, setTab] = useState('overview');
  return (
    <>
      <PageHead title="Admin panel" subtitle="System-wide controls for super admins." />
      <Tabs value={tab} onChange={setTab} tabs={[['overview', 'Overview'], ['businesses', 'Businesses'], ['users', 'All users'], ['roles', 'Roles & permissions'], ['database', 'Database'], ['audit', 'Audit logs'], ['config', 'Configuration']]} />
      {tab === 'overview' && <Overview />}
      {tab === 'businesses' && (
        <ManageTable endpoint="/admin/businesses" noun="business" canWrite defaultSort="created_at" searchPlaceholder="Search businesses"
          columns={[{ key: 'name', label: 'Business', sortable: true }, { key: 'industry', label: 'Industry' }, { key: 'users', label: 'Users', align: 'right' },
            { key: 'is_sample_data', label: 'Data', render: (r) => <Pill tone={r.is_sample_data ? 'warn' : 'good'}>{r.is_sample_data ? 'Sample' : 'Live'}</Pill> },
            { key: 'is_active', label: 'Status', render: (r) => <Pill tone={r.is_active ? 'good' : 'bad'}>{r.is_active ? 'Active' : 'Suspended'}</Pill> }]}
          fields={[{ key: 'name', label: 'Name', required: true }, { key: 'industry', label: 'Industry' }, { key: 'email', label: 'Email', type: 'email' }, { key: 'is_active', label: 'Active', type: 'checkbox', checkLabel: 'Business is active' }]} readOnly={false} />)}
      {tab === 'users' && (
        <ManageTable endpoint="/users" noun="user" defaultSort="created_at" searchPlaceholder="Search all users"
          columns={[{ key: 'full_name', label: 'Name' }, { key: 'email', label: 'Email' }, { key: 'business_name', label: 'Business' }, { key: 'role_label', label: 'Role' },
            { key: 'is_active', label: 'Status', render: (r) => (r.is_active ? 'Active' : 'Inactive') }]} />)}
      {tab === 'roles' && <Roles />}
      {tab === 'database' && <Database />}
      {tab === 'audit' && (
        <ManageTable endpoint="/audit-logs" noun="log entry" defaultSort="created_at" searchPlaceholder="Search action or details"
          columns={[{ key: 'created_at', label: 'When', sortable: true, render: (r) => f.dateTime(r.created_at) }, { key: 'user', label: 'User' }, { key: 'action', label: 'Action', sortable: true },
            { key: 'entity', label: 'Entity' }, { key: 'details', label: 'Details' }, { key: 'ip', label: 'IP' }]} />)}
      {tab === 'config' && <Config />}
    </>
  );
}
