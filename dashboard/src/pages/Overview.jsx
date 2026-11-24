import React, { useState } from 'react';
import {
  AlertTriangle, ArrowUpCircle, CheckCircle2, Clock, FileText, RefreshCcw, Timer, Users,
} from 'lucide-react';
import ComplaintDrawer from '../components/ComplaintDrawer';
import DataTable from '../components/DataTable';
import { BarsChart, DonutChart, TrendChart } from '../components/Charts';
import { ErrorState, LoadingBlock } from '../components/feedback';
import { Button } from '../components/controls';
import {
  Card, CardHeader, LevelBadge, SeverityBadge, StatCard, StatusBadge,
} from '../components/ui';
import { useFetch } from '../hooks/useFetch';
import { fmtDateTime, minutesLabel, relativeTime } from '../lib/utils';
import { AnalyticsApi } from '../services/apiV2';

export default function Overview({ token, onNavigate }) {
  const [selected, setSelected] = useState(null);
  const { data, loading, error, reload } = useFetch(() => AnalyticsApi.dashboard(14), []);

  if (loading) return <LoadingBlock label="Loading district overview…" />;
  if (error) return <ErrorState message={error} onRetry={reload} />;

  const kpis = data?.kpis || {};
  const departments = (data?.departments || []).map((row) => ({ ...row, label: row.code }));
  const statusData = (data?.status_distribution || []).map((row) => ({
    name: String(row.status).replace(/_/g, ' '),
    value: row.count,
  }));

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between gap-2">
        <p className="text-[11px] text-slate-500">
          Last 14 days · {kpis.officers ?? 0} officers · {kpis.needs_review ?? 0} awaiting review
        </p>
        <Button variant="secondary" size="sm" onClick={reload}>
          <RefreshCcw size={12} /> Refresh
        </Button>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <StatCard label="Total" value={kpis.total} tone="navy" icon={FileText}
          onClick={() => onNavigate('complaints')} />
        <StatCard label="Open" value={kpis.pending} tone="blue" icon={Clock}
          hint={`${kpis.in_progress ?? 0} in progress`} onClick={() => onNavigate('complaints')} />
        <StatCard label="Past TAT" value={kpis.overdue} tone="red" icon={Timer}
          onClick={() => onNavigate('escalation')} />
        <StatCard label="Escalated" value={kpis.escalated} tone="amber" icon={ArrowUpCircle}
          onClick={() => onNavigate('escalation')} />
        <StatCard label="New" value={kpis.new} tone="violet" icon={FileText} />
        <StatCard label="Resolved" value={kpis.resolved} tone="green" icon={CheckCircle2} />
        <StatCard label="Needs review" value={kpis.needs_review} tone="slate" icon={AlertTriangle}
          onClick={() => onNavigate('escalation')} />
        <StatCard label="Officers" value={kpis.officers} tone="blue" icon={Users}
          onClick={() => onNavigate('officers')} />
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
        <Card className="xl:col-span-2">
          <CardHeader title="Received and resolved" subtitle="Daily count" />
          <div className="px-2 py-3"><TrendChart data={data?.trend || []} /></div>
        </Card>
        <Card>
          <CardHeader title="By status" />
          <div className="px-2 py-3">
            {statusData.length
              ? <DonutChart data={statusData} nameKey="name" valueKey="value" />
              : <p className="py-14 text-center text-[11px] text-slate-500">No complaints yet</p>}
          </div>
        </Card>
      </div>


      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
        <Card className="xl:col-span-2">
          <CardHeader title="By department" subtitle="Open, resolved and past TAT"
            actions={<Button size="sm" variant="ghost" onClick={() => onNavigate('departments')}>
              Departments
            </Button>} />

          <div className="px-2 py-3">
            {departments.length ? (
              <BarsChart data={departments} xKey="label" height={260}
                series={[
                  { key: 'open', name: 'Open', color: '#2563eb' },
                  { key: 'resolved', name: 'Resolved', color: '#10b981' },
                  { key: 'overdue', name: 'Overdue', color: '#dc2626' },
                ]} />
            ) : <p className="py-16 text-center text-xs text-slate-500">No departments configured</p>}
          </div>
        </Card>

        <Card>
          <CardHeader title="Last escalations" />

          <ul className="divide-y divide-slate-100 max-h-[268px] overflow-y-auto">
            {(data?.recent_escalations || []).length === 0 && (
              <li className="px-5 py-8 text-center text-xs text-slate-500">No escalations recorded</li>
            )}
            {(data?.recent_escalations || []).map((esc, index) => (
              <li key={index} className="px-5 py-2.5">
                <button onClick={() => setSelected(esc.complaint_id)}
                  className="text-xs font-semibold text-blue-700 hover:underline">
                  {esc.ticket_ref}
                </button>
                <p className="text-[11px] text-slate-600">
                  L{esc.from_level} → L{esc.to_level} · {esc.automatic ? 'automatic' : 'manual'}
                </p>
                <p className="text-[10px] text-slate-400">{relativeTime(esc.at)}</p>
              </li>
            ))}
          </ul>
        </Card>
      </div>

      <Card>
        <CardHeader title="Latest complaints"
          actions={<Button size="sm" variant="ghost" onClick={() => onNavigate('complaints')}>
            All complaints
          </Button>} />

        <DataTable
          rows={data?.recent || []}
          pageSize={6}
          onRowClick={(row) => setSelected(row.id)}
          columns={[
            { key: 'ticket_ref', label: 'Complaint', sortable: true,
              render: (row) => (
                <span className="font-mono text-[11px] font-medium text-slate-900">{row.ticket_ref}</span>
              ) },

            { key: 'category', label: 'Category', sortable: true },
            { key: 'department', label: 'Department' },
            { key: 'severity', label: 'Priority', sortable: true,
              render: (row) => <SeverityBadge severity={row.severity} /> },
            { key: 'status', label: 'Status', render: (row) => <StatusBadge status={row.status} /> },
            { key: 'level', label: 'Level', render: (row) => <LevelBadge level={row.level} /> },
            { key: 'created_at', label: 'Received', sortable: true,
              render: (row) => <span className="text-xs text-slate-500">{fmtDateTime(row.created_at)}</span> },
          ]}
        />
      </Card>

      <Card>
        <CardHeader title="High priority, still open" />
        <DataTable
          rows={data?.critical || []}
          pageSize={6}
          emptyTitle="Nothing high-priority is open"
          emptyMessage="Complaints marked High or Critical appear here until they are closed."

          onRowClick={(row) => setSelected(row.id)}
          columns={[
            { key: 'ticket_ref', label: 'Complaint',
              render: (row) => (
                <span className="font-mono text-[11px] font-medium text-slate-900">{row.ticket_ref}</span>
              ) },

            { key: 'department', label: 'Department' },
            { key: 'area', label: 'Location' },
            { key: 'severity', label: 'Priority',
              render: (row) => <SeverityBadge severity={row.severity} /> },
            { key: 'status', label: 'Status', render: (row) => <StatusBadge status={row.status} /> },
            { key: 'assigned_officer', label: 'Officer' },
            { key: 'minutes_remaining', label: 'TAT', align: 'right',
              render: (row) => (
                <span className={row.overdue ? 'text-xs font-semibold text-red-600' : 'text-xs text-slate-600'}>
                  {minutesLabel(row.minutes_remaining)}
                </span>
              ) },
          ]}
        />
      </Card>

      <ComplaintDrawer complaintId={selected} token={token} onClose={() => setSelected(null)}
        onChanged={reload} />
    </div>
  );
}

