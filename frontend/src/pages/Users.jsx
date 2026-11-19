import { useState } from 'react';
import { History, Power } from '../icons';
import api, { errMsg } from '../api/client';
import DataTable from '../components/DataTable';
import ManageTable from '../components/ManageTable';
import { Async, Modal, PageHead, Pill } from '../components/UI';
import { useAuth } from '../contexts/AuthContext';
import { useToast } from '../contexts/ToastContext';
import useFetch from '../hooks/useFetch';
import useFormat from '../hooks/useFormat';

const LABEL = { super_admin: 'Super Admin', business_admin: 'Business Admin', manager: 'Manager', analyst: 'Analyst', user: 'Standard User' };

function Activity({ user, onClose }) {
  const f = useFormat(); const { data, loading, error, reload } = useFetch(`/users/${user.id}/activity`, { per_page: 20 });
  return (
    <Modal title={`Activity: ${user.full_name}`} onClose={onClose} width={640}>
      <Async loading={loading} error={error} onRetry={reload} empty={data && !data.items.length} emptyProps={{ title: 'No activity recorded' }}>
        <DataTable dense rows={data?.items} columns={[{ key: 'created_at', label: 'When', render: (r) => f.dateTime(r.created_at) }, { key: 'action', label: 'Action' }, { key: 'entity', label: 'Entity' }, { key: 'details', label: 'Details' }]} />
      </Async>
    </Modal>
  );
}

export default function Users() {
  const { user: me } = useAuth(); const toast = useToast(); const f = useFormat();
  const [tick, setTick] = useState(0); const [viewing, setViewing] = useState(null);
  const toggle = async (u) => { try { await api.patch(`/users/${u.id}/status`); toast.success(u.is_active ? 'Account deactivated' : 'Account activated'); setTick(tick + 1); } catch (e) { toast.error(errMsg(e)); } };
  const { data: biz } = useFetch('/admin/businesses', { per_page: 100 }, { enabled: me.role === 'super_admin' });
  const bizOpts = (biz?.items || []).map((b) => ({ value: b.id, label: b.name }));
  const roleOpts = (d) => (d?.roles || []).map((r) => ({ value: r, label: LABEL[r] }));
  return (
    <>
      <PageHead title="Users" subtitle="Add team members, assign roles and review what they do." />
      <ManageTable key={tick} endpoint="/users" noun="user" canWrite defaultSort="created_at" searchPlaceholder="Search name or email"
        filters={[{ key: 'role', label: 'All roles', options: roleOpts }, { key: 'status', label: 'Any status', options: [{ value: 'active', label: 'Active' }, { value: 'inactive', label: 'Inactive' }] }]}
        columns={[{ key: 'full_name', label: 'Name', sortable: true }, { key: 'email', label: 'Email', sortable: true }, { key: 'role', label: 'Role', render: (r) => <Pill tone="info">{r.role_label}</Pill> },
          { key: 'is_active', label: 'Status', render: (r) => <Pill tone={r.is_active ? 'good' : 'bad'}>{r.is_active ? 'Active' : 'Inactive'}</Pill> },
          { key: 'last_login', label: 'Last sign-in', sortable: true, render: (r) => (r.last_login ? f.date(r.last_login) : 'Never') }]}
        fields={[{ key: 'full_name', label: 'Full name', required: true }, { key: 'email', label: 'Email', type: 'email', required: true },
          { key: 'role', label: 'Role', type: 'select', required: true, options: roleOpts, default: 'user' },
          ...(me.role === 'super_admin' ? [{ key: 'business_id', label: 'Business', type: 'select', options: bizOpts, asNumber: true, createOnly: true, hint: 'Defaults to your own business.' }] : []),
          { key: 'password', label: 'Password', type: 'password', hint: 'Required for new users. Leave blank on edit to keep the current one.' },
          { key: 'is_active', label: 'Active', type: 'checkbox', checkLabel: 'Account is active' }]}
        extraActions={(r) => (<>
          <button className="icon-btn" aria-label="View activity" onClick={() => setViewing(r)}><History size={16} /></button>
          {r.id !== me.id && <button className="icon-btn" aria-label={r.is_active ? 'Deactivate account' : 'Activate account'} onClick={() => toggle(r)}><Power size={16} /></button>}</>)} />
      {viewing && <Activity user={viewing} onClose={() => setViewing(null)} />}
    </>
  );
}
