import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { ShieldAlert } from '../icons';
import { useAuth } from '../contexts/AuthContext';
import { EmptyState, SkeletonBlock } from './UI';

export default function ProtectedRoute({ permission }) {
  const { user, loading, can } = useAuth();
  const loc = useLocation();
  if (loading) return <div style={{ padding: 40 }}><SkeletonBlock rows={5} /></div>;
  if (!user) return <Navigate to="/login" replace state={{ from: loc.pathname }} />;
  if (permission && !can(permission)) {
    return <EmptyState icon={ShieldAlert} title="You don't have access to this page" message="Ask a business admin to change your role if you need it." />;
  }
  return <Outlet />;
}
