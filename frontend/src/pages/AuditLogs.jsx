import ManageTable from '../components/ManageTable';
import { PageHead } from '../components/UI';
import useFormat from '../hooks/useFormat';

export default function AuditLogs() {
  const f = useFormat();
  return (
    <>
      <PageHead title="Audit log" subtitle="Who did what in your business, newest first." />
      <ManageTable endpoint="/audit-logs" noun="log entry" defaultSort="created_at" searchPlaceholder="Search action, entity or details"
        filters={[{ key: 'action', label: 'All actions', options: ['login', 'login_failed', 'create', 'update', 'delete', 'status', 'export', 'generate', 'deactivate', 'activate', 'password_change'] }]}
        columns={[{ key: 'created_at', label: 'When', sortable: true, render: (r) => f.dateTime(r.created_at) }, { key: 'user', label: 'User' },
          { key: 'action', label: 'Action', sortable: true }, { key: 'entity', label: 'Entity' }, { key: 'details', label: 'Details' }, { key: 'ip', label: 'IP' }]} />
    </>
  );
}
