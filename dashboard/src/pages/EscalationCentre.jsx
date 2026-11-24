import React, { useMemo, useState } from 'react';
import { ArrowUpCircle, ExternalLink, RefreshCcw } from 'lucide-react';
import ComplaintDrawer from '../components/ComplaintDrawer';
import DataTable from '../components/DataTable';
import { Button, Select } from '../components/controls';
import { ConfirmDialog, Tabs } from '../components/overlays';
import { Card, CardHeader, LevelBadge, SeverityBadge, StatCard, StatusBadge } from '../components/ui';
import { ErrorState, LoadingBlock } from '../components/feedback';
import { useToast } from '../components/Toast';
import { useFetch } from '../hooks/useFetch';
import { useConfirmDialog } from '../hooks/useConfirm';
import { canManage, minutesLabel } from '../lib/utils';
import { ComplaintApi, DepartmentApi, EscalationApi, apiErrorMessage } from '../services/apiV2';

const BUCKETS = [
  { key: 'pending_l1', label: 'L1 pending', count: 'l1' },
  { key: 'pending_l2', label: 'L2 pending', count: 'l2' },
  { key: 'pending_l3', label: 'L3 pending', count: 'l3' },
  { key: 'pending_l4', label: 'L4 pending', count: 'l4' },
  { key: 'overdue', label: 'Overdue', count: 'overdue' },
  { key: 'unacknowledged', label: 'Not acknowledged', count: 'unacknowledged' },
  { key: 'reopened', label: 'Reopened', count: 'reopened' },
  { key: 'needs_review', label: 'Needs review', count: 'needs_review' },
];

export default function EscalationCentre({ token }) {
  const toast = useToast();
  const { confirm, dialog } = useConfirmDialog();
  const [tab, setTab] = useState('pending_l1');
  const [departmentId, setDepartmentId] = useState('');
  const [severity, setSeverity] = useState('');
  const [selected, setSelected] = useState(null);
  const [busy, setBusy] = useState('');

  const centre = useFetch(() => EscalationApi.centre(), []);
  const departments = useFetch(() => DepartmentApi.list(), []);
  const manage = canManage(token);

  const escalate = async (complaint) => {
    const ok = await confirm({
      title: 'Escalate complaint?',
      message: `${complaint.ticket_ref} moves from L${complaint.level} to L${complaint.level + 1} and the next officer is notified.`,
      confirmLabel: 'Escalate',
      tone: 'primary',
    });
    if (!ok) return;
    setBusy(complaint.id);
    try {
      await ComplaintApi.escalate(complaint.id, 'manual escalation from escalation centre');
      toast.push(`${complaint.ticket_ref} escalated to L${complaint.level + 1}`, 'success');
      centre.reload();
    } catch (err) {
      toast.push(apiErrorMessage(err), 'error');
    } finally {
      setBusy('');
    }
  };

  const rows = useMemo(() => {
    let list = centre.data?.[tab] || [];
    if (departmentId) list = list.filter((row) => row.department_id === departmentId);
    if (severity) list = list.filter((row) => row.severity === severity);
    return list;
  }, [centre.data, tab, departmentId, severity]);

  if (centre.loading) return <LoadingBlock label="Loading escalation centre…" />;
  if (centre.error) return <ErrorState message={centre.error} onRetry={centre.reload} />;

  const counts = centre.data?.counts || {};

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <StatCard label="L1 pending" value={counts.l1 ?? 0} tone="blue" />
        <StatCard label="L2 pending" value={counts.l2 ?? 0} tone="violet" />
        <StatCard label="L3 pending" value={counts.l3 ?? 0} tone="amber" />
        <StatCard label="L4 pending" value={counts.l4 ?? 0} tone="navy" />
      </div>

      <Card>
        <CardHeader title="Workload by level"
          subtitle="Deadlines are held in the database; this page only reads them"

          actions={(
            <Button size="sm" variant="secondary" onClick={centre.reload}>
              <RefreshCcw size={13} /> Refresh
            </Button>
          )} />
        <div className="px-4 pt-3">
          <Tabs value={tab} onChange={setTab}
            tabs={BUCKETS.map((bucket) => ({
              value: bucket.key, label: bucket.label, count: counts[bucket.count] ?? 0,
            }))} />
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 p-4">
          <Select value={departmentId} onChange={(e) => setDepartmentId(e.target.value)}>
            <option value="">All departments</option>
            {(departments.data || []).map((dept) => (
              <option key={dept.id} value={dept.id}>{dept.name}</option>
            ))}
          </Select>
          <Select value={severity} onChange={(e) => setSeverity(e.target.value)}>
            <option value="">Any priority</option>
            <option value="High">High</option>
            <option value="Medium">Medium</option>
            <option value="Low">Low</option>
          </Select>
        </div>
        <DataTable
          rows={rows}
          pageSize={10}
          dense
          onRowClick={(row) => setSelected(row.id)}
          emptyTitle="Nothing pending"
          emptyMessage="Cases appear here when a TAT deadline passes."

          columns={[
            { key: 'ticket_ref', label: 'Complaint', sortable: true,
              render: (row) => (
                <span className="font-mono text-[11px] font-medium text-slate-900">{row.ticket_ref}</span>
              ) },

            { key: 'department', label: 'Department' },
            { key: 'area', label: 'Location',
              render: (row) => <span className="text-xs">{row.area || '—'}</span> },
            { key: 'severity', label: 'Priority',
              render: (row) => <SeverityBadge severity={row.severity} /> },
            { key: 'assigned_officer', label: 'Current officer',
              render: (row) => <span className="text-xs">{row.assigned_officer || 'Unassigned'}</span> },
            { key: 'level', label: 'Level', render: (row) => <LevelBadge level={row.level} /> },
            { key: 'status', label: 'Status', render: (row) => <StatusBadge status={row.status} /> },
            { key: 'minutes_remaining', label: 'TAT', align: 'right',
              render: (row) => (
                <span className={row.overdue ? 'text-[11px] font-semibold text-red-600'
                  : 'text-[11px] text-slate-600'}>
                  {minutesLabel(row.minutes_remaining)}
                </span>
              ) },
            { key: 'actions', label: '', align: 'right',
              render: (row) => (
                <div className="flex justify-end gap-2">
                  <button onClick={(event) => { event.stopPropagation(); setSelected(row.id); }}
                    className="inline-flex items-center gap-1 text-[11px] font-semibold text-blue-700 hover:underline">
                    Open <ExternalLink size={11} />
                  </button>
                  {manage && row.level < 4 && (
                    <button disabled={busy === row.id}
                      onClick={(event) => { event.stopPropagation(); escalate(row); }}
                      className="inline-flex items-center gap-1 text-[11px] font-semibold text-amber-700 hover:underline disabled:opacity-50">
                      <ArrowUpCircle size={11} /> Escalate
                    </button>
                  )}
                </div>
              ) },
          ]}
        />
      </Card>

      <ComplaintDrawer complaintId={selected} token={token} onClose={() => setSelected(null)}
        onChanged={centre.reload} />
      <ConfirmDialog {...dialog} loading={Boolean(busy)} />
    </div>
  );
}

