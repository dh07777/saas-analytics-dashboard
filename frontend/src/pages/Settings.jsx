import { useState } from 'react';
import api, { errMsg, fieldErrors } from '../api/client';
import { Confirm, Field, PageHead } from '../components/UI';
import { useAuth } from '../contexts/AuthContext';
import { useTheme } from '../contexts/ThemeContext';
import { useToast } from '../contexts/ToastContext';

const CURRENCIES = ['USD', 'EUR', 'GBP', 'INR', 'JPY', 'AUD', 'CAD', 'AED', 'SGD', 'BRL'];

export default function Settings() {
  const { user, setUser, can, refresh } = useAuth(); const toast = useToast(); const { setTheme } = useTheme();
  const canEdit = can('settings.edit');
  const [biz, setBiz] = useState(user.business || {}); const [be, setBe] = useState({});
  const [pref, setPref] = useState(user.settings); const [purge, setPurge] = useState(false);

  const saveBiz = async (e) => {
    e.preventDefault(); setBe({});
    try { const r = await api.put('/settings/business', biz); setUser({ ...user, business: r.data.business, business_name: r.data.business.name }); toast.success('Company settings saved'); }
    catch (err) { setBe(fieldErrors(err)); toast.error(errMsg(err)); }
  };
  const savePref = async (next) => {
    setPref(next);
    try { const r = await api.put('/settings/user', next); setUser({ ...user, settings: r.data.user }); if (next.theme) setTheme(next.theme); toast.success('Preferences saved'); }
    catch (err) { toast.error(errMsg(err)); }
  };
  const doPurge = async () => {
    try { await api.delete('/settings/sample-data'); toast.success('Sample data removed'); setPurge(false); await refresh(); }
    catch (err) { toast.error(errMsg(err)); setPurge(false); }
  };
  const b = (k) => (e) => setBiz({ ...biz, [k]: e.target.value });

  return (
    <>
      <PageHead title="Settings" subtitle="Company details and your personal preferences." />
      <div className="grid g-2">
        <form className="card" onSubmit={saveBiz}>
          <h2 style={{ marginBottom: 14 }}>Company profile</h2>
          {!canEdit && <p className="small muted">Only business admins can change company details.</p>}
          <fieldset disabled={!canEdit} style={{ border: 0, padding: 0, margin: 0 }}>
            <Field label="Company name" error={be.name} htmlFor="s-n"><input id="s-n" className="input" value={biz.name || ''} onChange={b('name')} /></Field>
            <Field label="Industry" htmlFor="s-i"><input id="s-i" className="input" value={biz.industry || ''} onChange={b('industry')} /></Field>
            <Field label="Business email" error={be.email} htmlFor="s-e"><input id="s-e" className="input" type="email" value={biz.email || ''} onChange={b('email')} /></Field>
            <Field label="Phone" htmlFor="s-p"><input id="s-p" className="input" value={biz.phone || ''} onChange={b('phone')} /></Field>
            <Field label="Address" htmlFor="s-a"><input id="s-a" className="input" value={biz.address || ''} onChange={b('address')} /></Field>
            <Field label="Currency" hint="Used for every amount in the app" htmlFor="s-c"><select id="s-c" className="input" value={biz.currency || 'USD'} onChange={b('currency')}>{CURRENCIES.map((c) => <option key={c}>{c}</option>)}</select></Field>
            {canEdit && <button className="btn primary">Save changes</button>}
          </fieldset>
        </form>
        <div style={{ display: 'grid', gap: 16, alignContent: 'start' }}>
          <div className="card">
            <h2 style={{ marginBottom: 14 }}>Preferences</h2>
            <Field label="Theme" htmlFor="p-t"><select id="p-t" className="input" value={pref.theme} onChange={(e) => savePref({ ...pref, theme: e.target.value })}><option value="light">Light</option><option value="dark">Dark</option></select></Field>
            <Field label="Date format" htmlFor="p-d"><select id="p-d" className="input" value={pref.date_format} onChange={(e) => savePref({ ...pref, date_format: e.target.value })}>{['YYYY-MM-DD', 'DD/MM/YYYY', 'MM/DD/YYYY'].map((d) => <option key={d}>{d}</option>)}</select></Field>
            <h3 style={{ margin: '4px 0 10px' }}>Notify me about</h3>
            {[['notify_revenue', 'Revenue changes'], ['notify_inventory', 'Low inventory'], ['notify_activity', 'Team activity']].map(([k, l]) => (
              <label key={k} className="check field"><input type="checkbox" checked={pref[k]} onChange={(e) => savePref({ ...pref, [k]: e.target.checked })} />{l}</label>))}
          </div>
          {canEdit && user.business?.is_sample_data && (
            <div className="card"><h2>Sample data</h2>
              <p className="muted">This workspace contains generated sample customers, products, orders and expenses. Remove them to start with a clean slate. Records you added yourself are kept.</p>
              <button className="btn danger" onClick={() => setPurge(true)}>Remove sample data</button></div>)}
        </div>
      </div>
      {purge && <Confirm title="Remove sample data?" message="All generated sample records will be deleted. This cannot be undone." confirmLabel="Remove sample data" onConfirm={doPurge} onClose={() => setPurge(false)} />}
    </>
  );
}
