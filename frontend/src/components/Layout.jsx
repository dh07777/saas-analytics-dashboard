import { useEffect, useRef, useState } from 'react';
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom';
import {
  BarChart3, Bell, Boxes, CreditCard, ScrollText, FileText, LayoutDashboard, LogOut, Menu, Moon, Receipt, Settings, ShieldCheck,
  ShoppingBag, Sun, TrendingUp, UserCircle, Users, UsersRound, Zap, Info,
} from '../icons';
import api, { BUSINESS_KEY } from '../api/client';
import { useAuth } from '../contexts/AuthContext';
import { useTheme } from '../contexts/ThemeContext';
import useFetch from '../hooks/useFetch';

const NAV = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard, perm: 'dashboard.view', end: true },
  { group: 'Analytics' },
  { to: '/revenue', label: 'Revenue', icon: TrendingUp, perm: 'analytics.view' },
  { to: '/customers', label: 'Customers', icon: UsersRound, perm: 'analytics.view' },
  { to: '/sales', label: 'Sales', icon: ShoppingBag, perm: 'analytics.view' },
  { to: '/products', label: 'Products', icon: Boxes, perm: 'analytics.view' },
  { group: 'Finance' },
  { to: '/expenses', label: 'Expenses', icon: Receipt, perm: 'analytics.view' },
  { to: '/transactions', label: 'Transactions', icon: CreditCard, perm: 'data.read' },
  { to: '/reports', label: 'Reports', icon: FileText, perm: 'reports.generate' },
  { group: 'Workspace' },
  { to: '/notifications', label: 'Notifications', icon: Bell },
  { to: '/users', label: 'Users', icon: Users, perm: 'users.manage' },
  { to: '/audit', label: 'Audit log', icon: ScrollText, perm: 'audit.view' },
  { to: '/settings', label: 'Settings', icon: Settings },
  { to: '/admin', label: 'Admin panel', icon: ShieldCheck, perm: 'admin.access' },
];

export default function Layout() {
  const { user, can, logout } = useAuth();
  const { theme, toggle } = useTheme();
  const [open, setOpen] = useState(false); const [menu, setMenu] = useState(false);
  const [unread, setUnread] = useState(0);
  const nav = useNavigate(); const loc = useLocation(); const menuRef = useRef(null);
  const { data: pub } = useFetch('/config/public');
  const isSuper = user.role === 'super_admin';
  const { data: bizList } = useFetch('/admin/businesses', { per_page: 100, sort: 'name', order: 'asc' }, { enabled: isSuper });
  const [bizSel, setBizSel] = useState(localStorage.getItem(BUSINESS_KEY) || '');
  const switchBiz = (v) => { if (v) localStorage.setItem(BUSINESS_KEY, v); else localStorage.removeItem(BUSINESS_KEY); setBizSel(v); window.location.reload(); };

  useEffect(() => { setOpen(false); setMenu(false); }, [loc.pathname]);
  useEffect(() => {
    let live = true;
    const poll = () => api.get('/notifications/unread-count').then((r) => live && setUnread(r.data.unread)).catch(() => {});
    poll(); const t = setInterval(poll, 30000);
    window.addEventListener('notifications:changed', poll);
    return () => { live = false; clearInterval(t); window.removeEventListener('notifications:changed', poll); };
  }, []);
  useEffect(() => {
    const close = (e) => { if (menuRef.current && !menuRef.current.contains(e.target)) setMenu(false); };
    document.addEventListener('mousedown', close); return () => document.removeEventListener('mousedown', close);
  }, []);

  const toggleTheme = () => {
    const next = theme === 'dark' ? 'light' : 'dark'; toggle();
    api.put('/settings/user', { theme: next }).catch(() => {});
  };
  const items = NAV.filter((n, i) => {
    if (n.group) { const rest = NAV.slice(i + 1); const nextGroup = rest.findIndex((x) => x.group); return rest.slice(0, nextGroup < 0 ? undefined : nextGroup).some((x) => !x.perm || can(x.perm)); }
    return !n.perm || can(n.perm);
  });

  return (
    <div className="shell">
      <aside className={`sidebar ${open ? 'open' : ''}`} aria-label="Main navigation">
        <div className="brand"><span className="brand-mark"><Zap size={18} /></span>InsightFlow</div>
        <nav className="nav">
          {items.map((n, i) => n.group ? <div key={i} className="nav-group">{n.group}</div> : (
            <NavLink key={n.to} to={n.to} end={n.end}><n.icon size={18} />{n.label}</NavLink>))}
        </nav>
        <div style={{ marginTop: 'auto', padding: '16px 10px 0', fontSize: '0.82rem' }}>
          <div style={{ color: '#fff', fontWeight: 600 }}>{user.business_name || 'No business'}</div>
          <div>{user.role_label}</div>
        </div>
      </aside>
      <div className={`scrim ${open ? 'open' : ''}`} onClick={() => setOpen(false)} />
      <div className="main">
        <header className="topbar">
          <button className="icon-btn menu-btn" aria-label="Open menu" onClick={() => setOpen(true)}><Menu size={20} /></button>
          <div className="spacer" />
          {isSuper && bizList && (
            <select className="input" style={{ width: 'auto', maxWidth: 240 }} aria-label="Business to view" value={bizSel} onChange={(e) => switchBiz(e.target.value)}>
              <option value="">My business</option>
              {bizList.items.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
            </select>)}
          <button className="icon-btn" aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`} onClick={toggleTheme}>{theme === 'dark' ? <Sun size={18} /> : <Moon size={18} />}</button>
          <button className="icon-btn" aria-label={`Notifications, ${unread} unread`} onClick={() => nav('/notifications')}>
            <Bell size={18} />{unread > 0 && <span className="dot">{unread > 99 ? '99+' : unread}</span>}
          </button>
          <div style={{ position: 'relative' }} ref={menuRef}>
            <button className="btn" onClick={() => setMenu(!menu)} aria-haspopup="menu" aria-expanded={menu}><UserCircle size={18} />{user.full_name.split(' ')[0]}</button>
            {menu && (
              <div className="menu" role="menu">
                <div className="small muted" style={{ padding: '6px 10px' }}>{user.email}</div>
                <NavLink to="/profile" role="menuitem"><UserCircle size={16} />Profile</NavLink>
                <NavLink to="/settings" role="menuitem"><Settings size={16} />Settings</NavLink>
                <button role="menuitem" onClick={async () => { await logout(); nav('/login'); }}><LogOut size={16} />Sign out</button>
              </div>)}
          </div>
        </header>
        {pub?.announcement && <div className="banner announce"><Info size={16} />{pub.announcement}</div>}
        {user.business?.is_sample_data && (
          <div className="banner sample"><BarChart3 size={16} />You're looking at SAMPLE data, not real business records.
            {can('settings.edit') && <NavLink to="/settings" style={{ marginLeft: 6 }}>Remove sample data</NavLink>}</div>)}
        <main className="content"><Outlet /></main>
      </div>
    </div>
  );
}
