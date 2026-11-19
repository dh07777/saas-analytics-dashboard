import { Navigate, Route, Routes } from 'react-router-dom';
import Layout from './components/Layout';
import ProtectedRoute from './components/ProtectedRoute';
import { EmptyState } from './components/UI';
import { ForgotPassword, Login, Register, ResetPassword } from './pages/AuthPages';
import Dashboard from './pages/Dashboard';
import Revenue from './pages/Revenue';
import Customers from './pages/Customers';
import Sales from './pages/Sales';
import Products from './pages/Products';
import Expenses from './pages/Expenses';
import Reports from './pages/Reports';
import Notifications from './pages/Notifications';
import Users from './pages/Users';
import Settings from './pages/Settings';
import Profile from './pages/Profile';
import Admin from './pages/Admin';
import Transactions from './pages/Transactions';
import AuditLogs from './pages/AuditLogs';

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />
      <Route path="/forgot-password" element={<ForgotPassword />} />
      <Route path="/reset-password" element={<ResetPassword />} />
      <Route element={<ProtectedRoute />}>
        <Route element={<Layout />}>
          <Route element={<ProtectedRoute permission="dashboard.view" />}><Route index element={<Dashboard />} /></Route>
          <Route element={<ProtectedRoute permission="analytics.view" />}>
            <Route path="revenue" element={<Revenue />} />
            <Route path="customers" element={<Customers />} />
            <Route path="sales" element={<Sales />} />
            <Route path="products" element={<Products />} />
            <Route path="expenses" element={<Expenses />} />
          </Route>
          <Route element={<ProtectedRoute permission="data.read" />}><Route path="transactions" element={<Transactions />} /></Route>
          <Route element={<ProtectedRoute permission="audit.view" />}><Route path="audit" element={<AuditLogs />} /></Route>
          <Route element={<ProtectedRoute permission="reports.generate" />}><Route path="reports" element={<Reports />} /></Route>
          <Route element={<ProtectedRoute permission="users.manage" />}><Route path="users" element={<Users />} /></Route>
          <Route element={<ProtectedRoute permission="admin.access" />}><Route path="admin" element={<Admin />} /></Route>
          <Route path="notifications" element={<Notifications />} />
          <Route path="settings" element={<Settings />} />
          <Route path="profile" element={<Profile />} />
          <Route path="*" element={<EmptyState title="Page not found" message="Check the address or use the menu." />} />
        </Route>
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
