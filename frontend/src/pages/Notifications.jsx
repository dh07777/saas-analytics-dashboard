import { useState } from 'react';
import { AlertTriangle, Bell, CheckCheck, CheckCircle2, Info, PackageX, Trash2, XCircle } from '../icons';
import api, { errMsg } from '../api/client';
import { Async, EmptyState, PageHead, Pill } from '../components/UI';
import { useToast } from '../contexts/ToastContext';
import useFetch from '../hooks/useFetch';
import useFormat from '../hooks/useFormat';

const ICON = { info: Info, success: CheckCircle2, warning: AlertTriangle, danger: XCircle };
const TYPES = [['', 'All'], ['inventory', 'Inventory'], ['revenue', 'Revenue'], ['activity', 'Activity'], ['system', 'System']];

export default function Notifications() {
  const toast = useToast(); const f = useFormat();
  const [type, setType] = useState(''); const [unread, setUnread] = useState(false); const [page, setPage] = useState(1);
  const { data, loading, error, reload } = useFetch('/notifications', { type, unread: unread ? 1 : undefined, page, per_page: 15 });
  const changed = () => { reload(); window.dispatchEvent(new Event('notifications:changed')); };
  const call = async (fn, msg) => { try { await fn(); if (msg) toast.success(msg); changed(); } catch (e) { toast.error(errMsg(e)); } };

  return (
    <>
      <PageHead title="Notifications" subtitle="Business alerts, stock warnings and team activity. Refreshes every 30 seconds.">
        <button className="btn" disabled={!data?.unread} onClick={() => call(() => api.post('/notifications/read-all'), 'All caught up')}><CheckCheck size={16} />Mark all read</button>
      </PageHead>
      <div className="toolbar" style={{ marginBottom: 14 }}>
        <div className="seg" role="group" aria-label="Type">{TYPES.map(([v, l]) => <button key={v} className={type === v ? 'on' : ''} onClick={() => { setType(v); setPage(1); }}>{l}</button>)}</div>
        <label className="check"><input type="checkbox" checked={unread} onChange={(e) => { setUnread(e.target.checked); setPage(1); }} />Unread only</label>
      </div>
      <div className="card">
        <Async loading={loading && !data} error={error} onRetry={reload} empty={data && !data.items.length}
          emptyProps={{ icon: Bell, title: 'No notifications', message: unread ? 'You have read everything.' : 'Alerts for low stock and revenue changes will appear here.' }}>
          {data?.items.map((n) => { const I = n.type === 'inventory' && n.severity === 'danger' ? PackageX : ICON[n.severity] || Info; return (
            <div key={n.id} className={`list-row ${n.is_read ? '' : 'unread'}`}>
              <I size={20} color={`var(--${{ danger: 'bad', warning: 'warn', success: 'good', info: 'info' }[n.severity] || 'info'})`} style={{ flexShrink: 0, marginTop: 2 }} />
              <div style={{ flex: 1 }}><strong>{n.title}</strong> <Pill>{n.type}</Pill><div className="muted small">{n.message}</div><div className="small muted">{f.dateTime(n.created_at)}</div></div>
              <div className="toolbar" style={{ flexWrap: 'nowrap' }}>
                {!n.is_read && <button className="btn sm" onClick={() => call(() => api.patch(`/notifications/${n.id}/read`))}>Mark read</button>}
                <button className="icon-btn" aria-label="Delete notification" onClick={() => call(() => api.delete(`/notifications/${n.id}`), 'Notification deleted')}><Trash2 size={16} /></button></div>
            </div>); })}
          {data?.pages > 1 && <div className="pager"><span className="small muted">Page {page} of {data.pages}</span><div className="toolbar"><button className="btn sm" disabled={page <= 1} onClick={() => setPage(page - 1)}>Previous</button><button className="btn sm" disabled={page >= data.pages} onClick={() => setPage(page + 1)}>Next</button></div></div>}
        </Async>
      </div>
    </>
  );
}
