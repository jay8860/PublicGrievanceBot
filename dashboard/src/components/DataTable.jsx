// Sortable, paginated data table with loading / empty / error states.
import React, { useEffect, useMemo, useState } from 'react';
import { ArrowDown, ArrowUp, ChevronsUpDown } from 'lucide-react';
import { cls } from '../lib/utils';
import { EmptyState, ErrorState, LoadingBlock } from './feedback';
import { Pagination } from './overlays';

export default function DataTable({
  columns, rows = [], loading, error, onRetry, onRowClick, rowKey = 'id',
  initialSort, pageSize = 10, emptyTitle = 'No records found', emptyMessage,
  toolbar, dense = false, footerNote,
}) {
  const [sort, setSort] = useState(initialSort || null);
  const [page, setPage] = useState(1);

  useEffect(() => { setPage(1); }, [rows.length, pageSize]);

  const sorted = useMemo(() => {
    if (!sort) return rows;
    const { key, direction } = sort;
    const factor = direction === 'asc' ? 1 : -1;
    return [...rows].sort((a, b) => {
      const left = a[key];
      const right = b[key];
      if (left === right) return 0;
      if (left === null || left === undefined) return 1;
      if (right === null || right === undefined) return -1;
      if (typeof left === 'number' && typeof right === 'number') return (left - right) * factor;
      return String(left).localeCompare(String(right)) * factor;
    });
  }, [rows, sort]);

  const paged = useMemo(
    () => sorted.slice((page - 1) * pageSize, page * pageSize),
    [sorted, page, pageSize]
  );

  const toggleSort = (column) => {
    if (!column.sortable) return;
    setSort((current) => {
      if (!current || current.key !== column.key) return { key: column.key, direction: 'asc' };
      return { key: column.key, direction: current.direction === 'asc' ? 'desc' : 'asc' };
    });
  };

  if (loading) return <LoadingBlock />;
  if (error) return <ErrorState message={error} onRetry={onRetry} />;

  return (
    <div>
      {toolbar && <div className="px-4 py-3 border-b border-slate-100">{toolbar}</div>}
      {rows.length === 0 ? (
        <EmptyState title={emptyTitle} message={emptyMessage} />
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead className="bg-slate-50 text-slate-500">
              <tr>
                {columns.map((column) => (
                  <th key={column.key}
                    onClick={() => toggleSort(column)}
                    style={column.width ? { width: column.width } : undefined}
                    className={cls('px-3 py-2 text-left text-[11px] font-medium text-slate-500',
                      column.align === 'right' && 'text-right',
                      column.sortable && 'cursor-pointer select-none hover:text-slate-700')}>
                    <span className={cls('inline-flex items-center gap-1', column.align === 'right' && 'justify-end w-full')}>
                      {column.label}
                      {column.sortable && (
                        sort?.key === column.key
                          ? (sort.direction === 'asc' ? <ArrowUp size={11} /> : <ArrowDown size={11} />)
                          : <ChevronsUpDown size={11} className="text-slate-300" />
                      )}
                    </span>
                  </th>
                ))}

              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {paged.map((row, index) => (
                <tr key={row[rowKey] || index}
                  onClick={onRowClick ? () => onRowClick(row) : undefined}
                  className={cls('bg-white', onRowClick && 'cursor-pointer hover:bg-slate-50')}>
                  {columns.map((column) => (
                    <td key={column.key}
                      className={cls('px-3 text-slate-700 align-middle border-b border-slate-100',
                        dense ? 'py-2' : 'py-2.5',
                        column.align === 'right' && 'text-right')}>
                      {column.render ? column.render(row) : (row[column.key] ?? '—')}
                    </td>
                  ))}
                </tr>
              ))}

            </tbody>
          </table>
        </div>
      )}
      {footerNote && (
        <p className="px-4 py-2 text-[11px] text-slate-500 border-t border-slate-100">{footerNote}</p>
      )}
      <Pagination page={page} pageSize={pageSize} total={rows.length} onPageChange={setPage} />
    </div>
  );
}
