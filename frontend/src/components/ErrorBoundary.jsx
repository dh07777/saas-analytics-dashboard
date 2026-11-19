import { Component } from 'react';

export default class ErrorBoundary extends Component {
  state = { error: null };
  static getDerivedStateFromError(error) { return { error }; }
  componentDidCatch(error, info) { console.error('UI crash:', error, info); }
  render() {
    if (!this.state.error) return this.props.children;
    return (
      <div style={{ maxWidth: 640, margin: '10vh auto', padding: 24, fontFamily: 'system-ui, sans-serif' }}>
        <h2>Something went wrong on this page</h2>
        <p>Try reloading. If it keeps happening, copy the message below.</p>
        <pre style={{ whiteSpace: 'pre-wrap', background: '#f3f3f3', color: '#222', padding: 12, borderRadius: 6 }}>{String(this.state.error?.stack || this.state.error)}</pre>
        <button onClick={() => { localStorage.clear(); window.location.href = '/'; }}>Clear saved session and reload</button>
      </div>
    );
  }
}
