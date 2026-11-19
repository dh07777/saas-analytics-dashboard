import { ArrowDown, ArrowUp, ChevronLeft, ChevronRight } from '../icons';
import { EmptyState } from './UI';

/** Presentational table. columns: [{key,label,render,sortable,align}] */
export default function DataTable({ columns, rows, sort, order, onSort, page, pages, total, onPage, emptyTitle, emptyMessage, rowKey = 'id', dense }) {
  if (!rows?.length) return <EmptyState title={emptyTitle || 'No results'} message={emptyMessage || 'Try changing your search or filters.'} />;
  return (
    <>
      <div className="table-wrap">
        <table className="table" style={dense ? { fontSize: '0.9rem' } : undefined}>
          <thead>
            <tr>
              {columns.map((c) => (
                <th key={c.key} className={`${c.sortable ? 'sortable' : ''} ${c.align === 'right' ? 'right' : ''}`}
                  aria-sort={sort === c.key ? (order === 'asc' ? 'ascending' : 'descending') : undefined}
                  onClick={c.sortable && onSort ? () => onSort(c.key) : undefined}>
                  {c.label}{sort === c.key && (order === 'asc' ? <ArrowUp size={12} /> : <ArrowDown size={12} />)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={r[rowKey] ?? i}>
                {columns.map((c) => <td key={c.key} className={c.align === 'right' ? 'right' : ''}>{c.render ? c.render(r) : r[c.key] ?? '—'}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {pages > 1 && onPage && (
        <div className="pager no-print">
          <span className="small muted">{total} results · page {page} of {pages}</span>
          <div className="toolbar">
            <button className="btn sm" disabled={page <= 1} onClick={() => onPage(page - 1)} aria-label="Previous page"><ChevronLeft size={16} /></button>
            <button className="btn sm" disabled={page >= pages} onClick={() => onPage(page + 1)} aria-label="Next page"><ChevronRight size={16} /></button>
          </div>
        </div>
      )}
    </>
  );
}
