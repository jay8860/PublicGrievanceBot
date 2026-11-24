import React, { useMemo, useState } from 'react';
import DataTable from '../components/DataTable';
import { SearchInput, Select } from '../components/controls';
import { Card, CardHeader } from '../components/ui';
import { ErrorState, LoadingBlock } from '../components/feedback';
import { useFetch } from '../hooks/useFetch';
import { fmtDateTime, titleCase } from '../lib/utils';
import { AuditApi } from '../services/apiV2';

const SOURCE_LABEL = {
  admin: 'Dashboard',
  officer: 'Officer',
  citizen: 'Citizen',
  system: 'System',
};

export default function AuditLogs() {
  const [search, setSearch] = useState('');
  const [entity, setEntity] = useState('');
  const [source, setSource] = useState('');

  const logs = useFetch(() => AuditApi.logs({ limit: 500 }), []);

  const rows = useMemo(() => {
    let list = logs.data || [];
    if (search.trim()) {
      const needle = search.trim().toLowerCase();
      list = list.filter((row) =>
        (row.action || '').toLowerCase().includes(needle)
        || (row.actor_id || '').toLowerCase().includes(needle)
        || (row.entity_id || '').toLowerCase().includes(needle));
    }
    if (entity) list = list.filter((row) => row.entity === entity);
    if (source) list = list.filter((row) => row.actor_type === source);
    return list;
  }, [logs.data, search, entity, source]);

  if (logs.loading) return <LoadingBlock label="Loading audit trail…" />;
  if (logs.error) return <ErrorState message={logs.error} onRetry={logs.reload} />;

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader title="Audit trail" subtitle={`${rows.length} entries, newest first`} />

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 p-4">
          <SearchInput value={search} onChange={setSearch} placeholder="Action, actor or record id…" />
          <Select value={entity} onChange={(e) => setEntity(e.target.value)}>
            <option value="">Any entity</option>
            <option value="complaint">Complaint</option>
            <option value="officer">Officer</option>
            <option value="department">Department</option>
            <option value="category">Category</option>
            <option value="admin_user">Admin account</option>
          </Select>
          <Select value={source} onChange={(e) => setSource(e.target.value)}>
            <option value="">Any source</option>
            <option value="admin">Dashboard (admin)</option>
            <option value="officer">Officer</option>
            <option value="citizen">Citizen</option>
            <option value="system">System / worker</option>
          </Select>
        </div>
        <DataTable
          rows={rows}
          pageSize={15}
          dense
          emptyTitle="No entries match"
          emptyMessage="Actions from the dashboard, Telegram and the escalation worker are recorded here."

          columns={[
            { key: 'at', label: 'Timestamp', sortable: true,
              render: (row) => <span className="text-[11px] text-slate-600">{fmtDateTime(row.at)}</span> },
            { key: 'action', label: 'Action', sortable: true,
              render: (row) => (
                <span className="text-xs font-semibold text-slate-800">{titleCase(row.action)}</span>
              ) },
            { key: 'entity', label: 'Record',
              render: (row) => (
                <div>
                  <p className="text-[11px] text-slate-700">{titleCase(row.entity || '—')}</p>
                  <p className="font-mono text-[10px] text-slate-400">{row.entity_id || '—'}</p>
                </div>
              ) },
            { key: 'actor', label: 'Performed by',
              render: (row) => (
                <div>
                  <p className="text-[11px] text-slate-700">{row.actor_id || 'system'}</p>
                  <p className="text-[10px] text-slate-400">
                    {SOURCE_LABEL[row.actor_type] || row.actor_type}
                  </p>
                </div>
              ) },
            { key: 'source', label: 'Source',
              render: (row) => (
                <span className="inline-flex rounded-md border border-slate-200 bg-slate-50 px-1.5 py-0.5 text-[10px] font-semibold text-slate-600">
                  {SOURCE_LABEL[row.actor_type] || row.actor_type}
                </span>
              ) },
            { key: 'detail', label: 'Details',
              render: (row) => {
                const entries = Object.entries(row.detail || {});
                if (entries.length === 0) return <span className="text-slate-300">—</span>;
                return (
                  <div className="max-w-[320px] space-y-0.5">
                    {entries.slice(0, 3).map(([key, value]) => (
                      <p key={key} className="truncate text-[10px] text-slate-500">
                        <span className="font-semibold text-slate-600">{key}:</span>{' '}
                        {typeof value === 'object' ? JSON.stringify(value) : String(value)}
                      </p>
                    ))}
                    {entries.length > 3 && (
                      <p className="text-[10px] text-slate-400">+{entries.length - 3} more</p>
                    )}
                  </div>
                );
              } },
          ]}
        />
      </Card>
    </div>
  );
}
