import React, { useEffect, useMemo, useState } from 'react';
import { Download, ExternalLink, ImageOff, RefreshCcw } from 'lucide-react';
import AuthImage from '../AuthImage';
import ComplaintDrawer from '../components/ComplaintDrawer';
import DataTable from '../components/DataTable';
import { LoadingBlock } from '../components/feedback';
import { Button, SearchInput, Select } from '../components/controls';
import { Card, CardHeader, LevelBadge, SeverityBadge, StatusBadge } from '../components/ui';
import { useToast } from '../components/Toast';
import { useFetch } from '../hooks/useFetch';
import { downloadBlob, fmtDateTime, minutesLabel, SEVERITY_OPTIONS, STATUS_OPTIONS } from '../lib/utils';
import { imageFor, imageSrc } from '../lib/media';
import { ComplaintApi, DepartmentApi, ReportApi, apiErrorMessage } from '../services/apiV2';

export default function Complaints({ token }) {
  const toast = useToast();
  const [search, setSearch] = useState('');
  const [appliedSearch, setAppliedSearch] = useState('');
  const [departmentId, setDepartmentId] = useState('');
  const [categoryId, setCategoryId] = useState('');
  const [status, setStatus] = useState('');
  const [severity, setSeverity] = useState('');
  const [level, setLevel] = useState('');
  const [overdue, setOverdue] = useState(false);
  const [selected, setSelected] = useState(null);
  const [exporting, setExporting] = useState('');

  useEffect(() => {
    const timer = setTimeout(() => setAppliedSearch(search.trim()), 350);
    return () => clearTimeout(timer);
  }, [search]);

  useEffect(() => { setCategoryId(''); }, [departmentId]);

  const departments = useFetch(() => DepartmentApi.list(), []);
  const categories = useFetch(
    () => (departmentId ? DepartmentApi.categories(departmentId) : Promise.resolve([])),
    [departmentId]
  );

  const params = useMemo(() => {
    const query = { limit: 500 };
    if (appliedSearch) query.search = appliedSearch;
    if (departmentId) query.department_id = departmentId;
    if (categoryId) query.category_id = categoryId;
    if (status) query.status = status;
    if (level) query.level = Number(level);
    if (overdue) query.overdue = true;
    return query;
  }, [appliedSearch, departmentId, categoryId, status, level, overdue]);

  const complaints = useFetch(() => ComplaintApi.list(params), [JSON.stringify(params)]);

  const rows = useMemo(() => {
    const items = complaints.data?.items || [];
    return severity ? items.filter((row) => row.severity === severity) : items;
  }, [complaints.data, severity]);

  const total = complaints.data?.total || 0;
  const filtersActive = Boolean(appliedSearch || departmentId || categoryId || status
    || severity || level || overdue);

  const reset = () => {
    setSearch(''); setAppliedSearch(''); setDepartmentId(''); setCategoryId('');
    setStatus(''); setSeverity(''); setLevel(''); setOverdue(false);
  };

  const exportCsv = async () => {
    setExporting('csv');
    try {
      const blob = await ReportApi.exportComplaints('csv',
        departmentId ? { department_id: departmentId } : {});
      downloadBlob(blob, `complaints-${new Date().toISOString().slice(0, 10)}.csv`);
      toast.push('CSV export downloaded', 'success');
    } catch (err) {
      toast.push(apiErrorMessage(err), 'error');
    } finally {
      setExporting('');
    }
  };

  if (departments.loading && complaints.loading) return <LoadingBlock label="Loading complaints…" />;

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader
          title="Filters"
          subtitle={filtersActive ? 'Filters applied' : 'No filters applied'}

          actions={(
            <div className="flex gap-2">
              <Button size="sm" variant="secondary" onClick={reset} disabled={!filtersActive}>
                Reset
              </Button>
              <Button size="sm" variant="secondary" loading={exporting === 'csv'} onClick={exportCsv}>
                <Download size={13} /> CSV
              </Button>
              <Button size="sm" variant="secondary" onClick={complaints.reload}>
                <RefreshCcw size={13} />
              </Button>
            </div>
          )}
        />
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 p-4">
          <SearchInput value={search} onChange={setSearch} placeholder="Search ticket, area or text…"
            className="sm:col-span-2" />
          <Select value={departmentId} onChange={(e) => setDepartmentId(e.target.value)}>
            <option value="">All departments</option>
            {(departments.data || []).map((dept) => (
              <option key={dept.id} value={dept.id}>{dept.name}</option>
            ))}
          </Select>
          <Select value={categoryId} onChange={(e) => setCategoryId(e.target.value)} disabled={!departmentId}>
            <option value="">{departmentId ? 'All categories' : 'Pick a department first'}</option>
            {(categories.data || []).map((category) => (
              <option key={category.id} value={category.id}>{category.name}</option>
            ))}
          </Select>
          <Select value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="">Any status</option>
            {STATUS_OPTIONS.map((option) => (
              <option key={option} value={option}>{option.replace(/_/g, ' ')}</option>
            ))}
          </Select>
          <Select value={severity} onChange={(e) => setSeverity(e.target.value)}>
            <option value="">Any priority</option>
            {SEVERITY_OPTIONS.map((option) => (
              <option key={option} value={option}>{option}</option>
            ))}
          </Select>
          <Select value={level} onChange={(e) => setLevel(e.target.value)}>
            <option value="">Any level</option>
            {[1, 2, 3, 4].map((option) => (
              <option key={option} value={option}>Level {option}</option>
            ))}
          </Select>
          <label className="flex items-center gap-2 text-xs font-medium text-slate-600 px-1">
            <input type="checkbox" checked={overdue} onChange={(e) => setOverdue(e.target.checked)}
              className="h-4 w-4 rounded border-slate-300 text-blue-700 focus:ring-blue-500" />
            Overdue only
          </label>
        </div>
      </Card>

      <Card>
        <CardHeader title={`Complaints (${total})`}
          subtitle={rows.length < total
            ? `Newest ${rows.length} of ${total}`
            : 'Newest first'} />

        <DataTable
          rows={rows}
          loading={complaints.loading}
          error={complaints.error}
          onRetry={complaints.reload}
          pageSize={12}
          dense
          onRowClick={(row) => setSelected(row.id)}
          emptyTitle="No complaints match"
          emptyMessage="Clear a filter or widen the period."

          columns={[
            { key: 'photo', label: 'Photo',
              render: (row) => {
                const src = imageSrc(imageFor(row.images, 'original'));
                return (
                  <div className="h-10 w-10 overflow-hidden rounded border border-slate-200 bg-slate-50">
                    {src
                      ? <AuthImage src={src} alt="" className="h-full w-full object-cover" />
                      : <span className="grid h-full w-full place-items-center text-slate-300">
                          <ImageOff size={14} />
                        </span>}
                  </div>
                );
              } },
            { key: 'ticket_ref', label: 'Complaint ID', sortable: true,
              render: (row) => (
                <div>
                  <p className="font-mono text-[11px] font-medium text-slate-900">{row.ticket_ref}</p>
                  <p className="text-[10px] text-slate-500">{fmtDateTime(row.created_at)}</p>
                </div>
              ) },

            { key: 'category', label: 'Category', sortable: true },
            { key: 'department', label: 'Department' },
            { key: 'area', label: 'Location',
              render: (row) => (
                <div className="max-w-[170px]">
                  <p className="truncate text-xs text-slate-700">{row.area || '—'}</p>
                  <p className="text-[10px] text-slate-400">
                    {row.ward || row.block || row.pincode || ''}
                  </p>
                </div>
              ) },
            { key: 'severity', label: 'Priority', sortable: true,
              render: (row) => <SeverityBadge severity={row.severity} /> },
            { key: 'assigned_officer', label: 'Officer',
              render: (row) => <span className="text-xs">{row.assigned_officer || 'Unassigned'}</span> },
            { key: 'level', label: 'Level', sortable: true,
              render: (row) => <LevelBadge level={row.level} /> },
            { key: 'status', label: 'Status',
              render: (row) => <StatusBadge status={row.status} /> },
            { key: 'minutes_remaining', label: 'TAT', align: 'right', sortable: true,
              render: (row) => (
                <span className={row.overdue ? 'text-[11px] font-semibold text-red-600'
                  : 'text-[11px] text-slate-600'}>
                  {['RESOLVED', 'CLOSED', 'VERIFIED'].includes(row.status)
                    ? 'Closed' : minutesLabel(row.minutes_remaining)}
                </span>
              ) },
            { key: 'actions', label: '', align: 'right',
              render: (row) => (
                <button onClick={(event) => { event.stopPropagation(); setSelected(row.id); }}
                  className="inline-flex items-center gap-1 text-[11px] font-semibold text-blue-700 hover:underline">
                  Open <ExternalLink size={11} />
                </button>
              ) },
          ]}
          footerNote={total > rows.length
            ? `Newest ${rows.length} of ${total} shown. Narrow the filters to see the rest.`
            : null}

        />
      </Card>

      <ComplaintDrawer complaintId={selected} token={token} onClose={() => setSelected(null)}
        onChanged={complaints.reload} />
    </div>
  );
}


