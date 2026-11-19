import { useState } from 'react';
import api, { errMsg, fieldErrors } from '../api/client';
import { Field, PageHead } from '../components/UI';
import { useAuth } from '../contexts/AuthContext';
import { useToast } from '../contexts/ToastContext';

export default function Profile() {
  const { user, setUser } = useAuth(); const toast = useToast();
  const [p, setP] = useState({ full_name: user.full_name, email: user.email }); const [pe, setPe] = useState({});
  const [pw, setPw] = useState({ current_password: '', new_password: '' }); const [we, setWe] = useState({});
  const saveProfile = async (e) => {
    e.preventDefault(); setPe({});
    try { setUser((await api.put('/auth/profile', p)).data.user); toast.success('Profile saved'); } catch (err) { setPe(fieldErrors(err)); toast.error(errMsg(err)); }
  };
  const savePw = async (e) => {
    e.preventDefault(); setWe({});
    try { await api.post('/auth/change-password', pw); setPw({ current_password: '', new_password: '' }); toast.success('Password changed'); } catch (err) { setWe(fieldErrors(err)); toast.error(errMsg(err)); }
  };
  return (
    <>
      <PageHead title="Your profile" subtitle={`${user.role_label} at ${user.business_name || 'no business'}`} />
      <div className="grid g-2">
        <form className="card" onSubmit={saveProfile}><h2 style={{ marginBottom: 14 }}>Personal details</h2>
          <Field label="Full name" error={pe.full_name} htmlFor="pf-n"><input id="pf-n" className="input" value={p.full_name} onChange={(e) => setP({ ...p, full_name: e.target.value })} /></Field>
          <Field label="Email" error={pe.email} htmlFor="pf-e"><input id="pf-e" className="input" type="email" value={p.email} onChange={(e) => setP({ ...p, email: e.target.value })} /></Field>
          <button className="btn primary">Save changes</button></form>
        <form className="card" onSubmit={savePw}><h2 style={{ marginBottom: 14 }}>Change password</h2>
          <Field label="Current password" error={we.current_password} htmlFor="pw-c"><input id="pw-c" className="input" type="password" autoComplete="current-password" value={pw.current_password} onChange={(e) => setPw({ ...pw, current_password: e.target.value })} /></Field>
          <Field label="New password" error={we.new_password || we.password} hint="8+ characters with a letter and a number" htmlFor="pw-n"><input id="pw-n" className="input" type="password" autoComplete="new-password" value={pw.new_password} onChange={(e) => setPw({ ...pw, new_password: e.target.value })} /></Field>
          <button className="btn primary" disabled={!pw.current_password || !pw.new_password}>Update password</button></form>
      </div>
    </>
  );
}
