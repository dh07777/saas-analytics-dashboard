import { useEffect, useState } from 'react';
import { Link, Navigate, useLocation, useNavigate, useSearchParams } from 'react-router-dom';
import { Zap } from '../icons';
import api, { errMsg, fieldErrors } from '../api/client';
import { Field } from '../components/UI';
import { useAuth } from '../contexts/AuthContext';
import { useToast } from '../contexts/ToastContext';
import useFetch from '../hooks/useFetch';

function AuthShell({ title, subtitle, children }) {
  return (
    <div className="auth">
      <div className="auth-art">
        <div className="brand" style={{ padding: 0 }}><span className="brand-mark"><Zap size={18} /></span>InsightFlow</div>
        <div><h1>See what your business is really doing.</h1><p>Revenue, customers, products and expenses in one place, calculated from your own records.</p></div>
        <span className="small" style={{ color: 'var(--side-ink)' }}>Final-year project edition</span>
      </div>
      <div className="auth-form"><div><h2>{title}</h2><p className="muted" style={{ marginTop: 0 }}>{subtitle}</p>{children}</div></div>
    </div>
  );
}

function useSubmit(fn) {
  const [busy, setBusy] = useState(false); const [error, setError] = useState(''); const [fields, setFields] = useState({});
  const run = async (e) => {
    e.preventDefault(); setBusy(true); setError(''); setFields({});
    try { await fn(); } catch (err) { setError(errMsg(err)); setFields(fieldErrors(err)); } finally { setBusy(false); }
  };
  return { busy, error, fields, run };
}

function useBackendStatus() {
  const [ok, setOk] = useState(null);
  useEffect(() => { api.get('/health').then(() => setOk(true)).catch(() => setOk(false)); }, []);
  return ok;
}

export function Login() {
  const { user, login } = useAuth(); const nav = useNavigate(); const loc = useLocation(); const backend = useBackendStatus();
  const [email, setEmail] = useState(''); const [password, setPassword] = useState('');
  const { busy, error, run } = useSubmit(async () => { await login(email, password); nav(loc.state?.from || '/', { replace: true }); });
  if (user) return <Navigate to="/" replace />;
  return (
    <AuthShell title="Sign in" subtitle="Welcome back. Enter your details to continue.">
      {backend === false && <p role="alert" className="bad" style={{ marginTop: 0 }}>The backend is not reachable. In the backend folder run <code>flask --app run seed</code> once, then <code>python run.py</code>.</p>}
      <form onSubmit={run} noValidate>
        <Field label="Email" htmlFor="email"><input id="email" className="input" type="email" autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} required /></Field>
        <Field label="Password" htmlFor="password"><input id="password" className="input" type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required /></Field>
        {error && <p role="alert" className="bad" style={{ marginTop: 0 }}>{error}</p>}
        <button className="btn primary block" disabled={busy || !email || !password}>{busy ? 'Signing in…' : 'Sign in'}</button>
        <p className="small" style={{ display: 'flex', justifyContent: 'space-between' }}><Link to="/forgot-password">Forgot password?</Link><Link to="/register">Create an account</Link></p>
      </form>
      <div className="demo-box">Demo accounts (password <code>Demo@1234</code>):<br />
        {['admin', 'manager', 'analyst', 'user', 'super'].map((r) => <button key={r} type="button" onClick={() => { setEmail(`${r}@insightflow.demo`); setPassword('Demo@1234'); }}>{r}</button>).reduce((a, b) => [a, ' · ', b])}
      </div>
    </AuthShell>
  );
}

export function Register() {
  const { user, register } = useAuth(); const nav = useNavigate();
  const { data: pub } = useFetch('/config/public');
  const [f, setF] = useState({ full_name: '', email: '', company_name: '', password: '' });
  const { busy, error, fields, run } = useSubmit(async () => { await register(f); nav('/', { replace: true }); });
  if (user) return <Navigate to="/" replace />;
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });
  return (
    <AuthShell title="Create your account" subtitle="You'll become the admin of a new, empty business workspace.">
      {pub && !pub.allow_registration ? <p className="bad">Registration is currently closed. Ask an administrator for an invite.</p> : (
        <form onSubmit={run} noValidate>
          <Field label="Full name" error={fields.full_name} htmlFor="full_name"><input id="full_name" className="input" value={f.full_name} onChange={set('full_name')} /></Field>
          <Field label="Company name" error={fields.company_name} htmlFor="company"><input id="company" className="input" value={f.company_name} onChange={set('company_name')} /></Field>
          <Field label="Work email" error={fields.email} htmlFor="reg-email"><input id="reg-email" className="input" type="email" value={f.email} onChange={set('email')} /></Field>
          <Field label="Password" error={fields.password} hint="8+ characters with a letter and a number" htmlFor="reg-pw"><input id="reg-pw" className="input" type="password" autoComplete="new-password" value={f.password} onChange={set('password')} /></Field>
          {error && !Object.keys(fields).length && <p role="alert" className="bad" style={{ marginTop: 0 }}>{error}</p>}
          <button className="btn primary block" disabled={busy}>{busy ? 'Creating…' : 'Create account'}</button>
        </form>)}
      <p className="small">Already registered? <Link to="/login">Sign in</Link></p>
    </AuthShell>
  );
}

export function ForgotPassword() {
  const [email, setEmail] = useState(''); const [sent, setSent] = useState(null);
  const { busy, error, run } = useSubmit(async () => { setSent((await api.post('/auth/forgot-password', { email })).data); });
  return (
    <AuthShell title="Reset your password" subtitle="Enter your email and we'll send a reset link.">
      {sent ? (
        <div>
          <p>{sent.message}</p>
          {sent.dev_reset_token && <div className="demo-box">Development mode (no email server): <Link to={`/reset-password?token=${sent.dev_reset_token}`}>open your reset link</Link></div>}
        </div>) : (
        <form onSubmit={run} noValidate>
          <Field label="Email" htmlFor="fp-email"><input id="fp-email" className="input" type="email" value={email} onChange={(e) => setEmail(e.target.value)} /></Field>
          {error && <p role="alert" className="bad" style={{ marginTop: 0 }}>{error}</p>}
          <button className="btn primary block" disabled={busy || !email}>{busy ? 'Sending…' : 'Send reset link'}</button>
        </form>)}
      <p className="small"><Link to="/login">Back to sign in</Link></p>
    </AuthShell>
  );
}

export function ResetPassword() {
  const [params] = useSearchParams(); const nav = useNavigate(); const toast = useToast();
  const [password, setPassword] = useState('');
  const { busy, error, fields, run } = useSubmit(async () => {
    await api.post('/auth/reset-password', { token: params.get('token') || '', password });
    toast.success('Password reset. Sign in with your new password.'); nav('/login');
  });
  return (
    <AuthShell title="Choose a new password" subtitle="Pick something you haven't used before.">
      <form onSubmit={run} noValidate>
        <Field label="New password" error={fields.password} hint="8+ characters with a letter and a number" htmlFor="np"><input id="np" className="input" type="password" autoComplete="new-password" value={password} onChange={(e) => setPassword(e.target.value)} /></Field>
        {error && <p role="alert" className="bad" style={{ marginTop: 0 }}>{error}</p>}
        <button className="btn primary block" disabled={busy || !password}>{busy ? 'Saving…' : 'Reset password'}</button>
      </form>
      <p className="small"><Link to="/forgot-password">Request a new link</Link></p>
    </AuthShell>
  );
}
