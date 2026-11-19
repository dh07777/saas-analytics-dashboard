import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { vi } from 'vitest';
import DataTable from '../components/DataTable';
import KpiCard from '../components/KpiCard';
import { Delta, EmptyState, ErrorState } from '../components/UI';
import ProtectedRoute from '../components/ProtectedRoute';
import { formatDate, makeFormatters } from '../hooks/useFormat';
import { presetRange } from '../utils/dates';

let authState = { user: null, loading: false, can: () => false };
vi.mock('../contexts/AuthContext', () => ({ useAuth: () => authState }));

describe('KpiCard', () => {
  it('shows label, value and growth', () => {
    render(<KpiCard label="Revenue" value="$1,000" change={12.5} />);
    expect(screen.getByText('Revenue')).toBeInTheDocument();
    expect(screen.getByText('$1,000')).toBeInTheDocument();
    expect(screen.getByText('+12.5%')).toBeInTheDocument();
  });
  it('explains missing comparison data', () => {
    render(<KpiCard label="Orders" value="0" change={null} />);
    expect(screen.getByText('No prior data')).toBeInTheDocument();
  });
});

describe('Delta', () => {
  it('uses the down style for negative growth', () => {
    const { container } = render(<Delta value={-4} />);
    expect(container.querySelector('.down')).toBeTruthy();
  });
  it('inverts colours for costs', () => {
    const { container } = render(<Delta value={5} invert />);
    expect(container.querySelector('.down')).toBeTruthy();
  });
});

describe('DataTable', () => {
  const columns = [{ key: 'name', label: 'Name', sortable: true }, { key: 'qty', label: 'Qty', align: 'right' }];
  it('renders rows', () => {
    render(<DataTable columns={columns} rows={[{ id: 1, name: 'Mug', qty: 3 }]} />);
    expect(screen.getByText('Mug')).toBeInTheDocument();
  });
  it('shows an empty state with no rows', () => {
    render(<DataTable columns={columns} rows={[]} emptyTitle="Nothing found" />);
    expect(screen.getByText('Nothing found')).toBeInTheDocument();
  });
  it('calls onSort when a sortable header is clicked', () => {
    const onSort = vi.fn();
    render(<DataTable columns={columns} rows={[{ id: 1, name: 'Mug', qty: 3 }]} onSort={onSort} />);
    fireEvent.click(screen.getByText('Name'));
    expect(onSort).toHaveBeenCalledWith('name');
  });
  it('paginates', () => {
    const onPage = vi.fn();
    render(<DataTable columns={columns} rows={[{ id: 1, name: 'Mug', qty: 3 }]} page={1} pages={3} total={30} onPage={onPage} />);
    fireEvent.click(screen.getByLabelText('Next page'));
    expect(onPage).toHaveBeenCalledWith(2);
    expect(screen.getByLabelText('Previous page')).toBeDisabled();
  });
});

describe('states', () => {
  it('error state offers retry', () => {
    const retry = vi.fn();
    render(<ErrorState message="Server down" onRetry={retry} />);
    fireEvent.click(screen.getByText('Try again'));
    expect(retry).toHaveBeenCalled();
    expect(screen.getByText('Server down')).toBeInTheDocument();
  });
  it('empty state shows a message', () => {
    render(<EmptyState title="No data" message="Add something" />);
    expect(screen.getByText('Add something')).toBeInTheDocument();
  });
});

describe('ProtectedRoute', () => {
  const renderAt = () => render(
    <MemoryRouter initialEntries={['/secret']}>
      <Routes>
        <Route path="/login" element={<div>login page</div>} />
        <Route element={<ProtectedRoute permission="analytics.view" />}><Route path="/secret" element={<div>secret page</div>} /></Route>
      </Routes>
    </MemoryRouter>);
  it('redirects anonymous visitors to login', () => {
    authState = { user: null, loading: false, can: () => false };
    renderAt();
    expect(screen.getByText('login page')).toBeInTheDocument();
  });
  it('blocks users without the permission', () => {
    authState = { user: { id: 1 }, loading: false, can: () => false };
    renderAt();
    expect(screen.getByText(/don't have access/i)).toBeInTheDocument();
  });
  it('allows users with the permission', () => {
    authState = { user: { id: 1 }, loading: false, can: (p) => p === 'analytics.view' };
    renderAt();
    expect(screen.getByText('secret page')).toBeInTheDocument();
  });
});

describe('formatting helpers', () => {
  it('formats dates in the chosen style', () => {
    expect(formatDate('2026-03-05T10:00:00', 'DD/MM/YYYY')).toBe('05/03/2026');
    expect(formatDate('2026-03-05T10:00:00', 'MM/DD/YYYY')).toBe('03/05/2026');
    expect(formatDate(null)).toBe('—');
  });
  it('formats money and percentages', () => {
    const f = makeFormatters('USD');
    expect(f.money(1234.5)).toContain('1,234.50');
    expect(f.pct(5)).toBe('+5%');
    expect(f.money(null)).toBe('—');
  });
  it('builds presets ending today', () => {
    const r = presetRange('7d');
    expect(r.start <= r.end).toBe(true);
  });
});
