import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { vi } from 'vitest';
import ManageTable from '../components/ManageTable';

const get = vi.fn(); const post = vi.fn();
vi.mock('../api/client', () => ({
  default: { get: (...a) => get(...a), post: (...a) => post(...a), put: vi.fn(), delete: vi.fn() },
  errMsg: (e) => e.message, fieldErrors: () => ({}),
}));
vi.mock('../contexts/ToastContext', () => ({ useToast: () => ({ success: vi.fn(), error: vi.fn(), info: vi.fn() }) }));

const columns = [{ key: 'name', label: 'Name' }];
const fields = [{ key: 'name', label: 'Name', required: true }];

beforeEach(() => {
  get.mockReset(); post.mockReset();
  get.mockResolvedValue({ data: { items: [{ id: 1, name: 'Acme' }], page: 1, pages: 1, total: 1 } });
});

it('lists rows from the API', async () => {
  render(<ManageTable endpoint="/things" noun="thing" columns={columns} fields={fields} canWrite />);
  expect(await screen.findByText('Acme')).toBeInTheDocument();
  expect(get).toHaveBeenCalledWith('/things', expect.objectContaining({ params: expect.objectContaining({ page: 1 }) }));
});

it('creates a record through the modal', async () => {
  post.mockResolvedValue({ data: { id: 2 } });
  render(<ManageTable endpoint="/things" noun="thing" columns={columns} fields={fields} canWrite />);
  await screen.findByText('Acme');
  fireEvent.click(screen.getByText('New thing'));
  fireEvent.change(screen.getByLabelText(/Name/, { selector: 'input#f-name' }), { target: { value: 'Globex' } });
  fireEvent.click(screen.getByText('Save changes'));
  await waitFor(() => expect(post).toHaveBeenCalledWith('/things', { name: 'Globex' }));
});

it('hides write actions for read-only users', async () => {
  render(<ManageTable endpoint="/things" noun="thing" columns={columns} fields={fields} canWrite={false} />);
  await screen.findByText('Acme');
  expect(screen.queryByText('New thing')).not.toBeInTheDocument();
});

it('shows an error state with retry when the API fails', async () => {
  get.mockRejectedValue(new Error('boom'));
  render(<ManageTable endpoint="/things" noun="thing" columns={columns} fields={fields} />);
  expect(await screen.findByText('Try again')).toBeInTheDocument();
});
