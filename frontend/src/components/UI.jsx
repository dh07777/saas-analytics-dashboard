import { AlertTriangle, Inbox, TrendingDown, TrendingUp, X } from '../icons';

export function Skeleton({ h = 16, w = '100%', style }) {
  return <div className="skeleton" style={{ height: h, width: w, ...style }} aria-hidden="true" />;
}

export function SkeletonBlock({ rows = 4 }) {
  return (
    <div role="status" aria-label="Loading" style={{ display: 'grid', gap: 10 }}>
      {Array.from({ length: rows }).map((_, i) => <Skeleton key={i} h={i === 0 ? 26 : 16} w={`${100 - i * 9}%`} />)}
    </div>
  );
}

export function EmptyState({ title = 'Nothing here yet', message, action, icon: Icon = Inbox }) {
  return (
    <div className="state">
      <Icon size={34} /><h3>{title}</h3>{message && <p style={{ margin: '0 0 12px' }}>{message}</p>}{action}
    </div>
  );
}

export function ErrorState({ message, onRetry }) {
  return (
    <div className="state" role="alert">
      <AlertTriangle size={34} color="var(--bad)" /><h3>Couldn't load this data</h3>
      <p style={{ margin: '0 0 12px' }}>{message}</p>
      {onRetry && <button className="btn" onClick={onRetry}>Try again</button>}
    </div>
  );
}

/** Wraps data-driven blocks with loading / error / empty handling. */
export function Async({ loading, error, onRetry, empty, emptyProps, rows = 4, children }) {
  if (loading) return <SkeletonBlock rows={rows} />;
  if (error) return <ErrorState message={error} onRetry={onRetry} />;
  if (empty) return <EmptyState {...emptyProps} />;
  return children;
}

export function Modal({ title, onClose, children, footer, width }) {
  return (
    <div className="modal-back" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="modal" role="dialog" aria-modal="true" aria-label={title} style={width ? { width } : undefined}>
        <div className="modal-head"><h2>{title}</h2><button className="icon-btn" aria-label="Close" onClick={onClose}><X size={18} /></button></div>
        <div className="modal-body">{children}</div>
        {footer && <div className="modal-foot">{footer}</div>}
      </div>
    </div>
  );
}

export function Confirm({ title, message, confirmLabel = 'Delete', onConfirm, onClose, busy }) {
  return (
    <Modal title={title} onClose={onClose} footer={<>
      <button className="btn" onClick={onClose}>Cancel</button>
      <button className="btn danger" disabled={busy} onClick={onConfirm}>{confirmLabel}</button></>}>
      <p style={{ margin: 0 }}>{message}</p>
    </Modal>
  );
}

export function Tabs({ tabs, value, onChange }) {
  return (
    <div className="tabs" role="tablist">
      {tabs.map(([id, label]) => (
        <button key={id} role="tab" aria-selected={value === id} className={value === id ? 'on' : ''} onClick={() => onChange(id)}>{label}</button>
      ))}
    </div>
  );
}

export function Pill({ tone, children }) { return <span className={`pill ${tone || ''}`}>{children}</span>; }

export function Delta({ value, suffix = '%', invert = false }) {
  if (value == null) return <span className="delta flat">No prior data</span>;
  const up = value > 0; const good = invert ? !up : up;
  const cls = value === 0 ? 'flat' : good ? 'up' : 'down';
  const I = up ? TrendingUp : TrendingDown;
  return <span className={`delta ${cls}`}>{value !== 0 && <I size={15} />}{value > 0 ? '+' : ''}{value}{suffix}</span>;
}

export function Field({ label, error, hint, children, htmlFor }) {
  return (
    <div className="field">
      {label && <label htmlFor={htmlFor}>{label}</label>}
      {children}
      {error && <span className="err">{error}</span>}
      {!error && hint && <span className="hint">{hint}</span>}
    </div>
  );
}

export function PageHead({ title, subtitle, children }) {
  return (
    <div className="page-head">
      <div><h1>{title}</h1>{subtitle && <p>{subtitle}</p>}</div>
      <div className="toolbar no-print">{children}</div>
    </div>
  );
}
