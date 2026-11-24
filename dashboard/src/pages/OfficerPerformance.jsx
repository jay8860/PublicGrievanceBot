import React, { useMemo, useState } from 'react';
import { Star } from 'lucide-react';
import DataTable from '../components/DataTable';
import { BarsChart } from '../components/Charts';
import { Select } from '../components/controls';
import { Card, CardHeader, LevelBadge, StatCard } from '../components/ui';
import { ErrorState, LoadingBlock } from '../components/feedback';
import { useFetch } from '../hooks/useFetch';
import { hours } from '../lib/utils';
import { AnalyticsApi, DepartmentApi } from '../services/apiV2';

export default function OfficerPerformance() {
  const [departmentId, setDepartmentId] = useState('');
  const [level, setLevel] = useState('');

  const performance = useFetch(() => AnalyticsApi.performance(), []);
  const departments = useFetch(() => DepartmentApi.list(), []);

  const rows = useMemo(() => {
    let list = performance.data || [];
    if (departmentId) {
      const deptName = (departments.data || []).find((dept) => dept.id === departmentId)?.name;
      list = list.filter((row) => row.department === deptName);
    }
    if (level) list = list.filter((row) => row.level === Number(level));
    return list;
  }, [performance.data, departmentId, level, departments.data]);

  const totals = useMemo(() => {
    const sum = (key) => rows.reduce((acc, row) => acc + (row[key] || 0), 0);
    const rated = rows.filter((row) => row.avg_rating != null);
    const timed = rows.filter((row) => row.avg_resolution_hours != null);
    return {
      open: sum('open'),
      resolved: sum('resolved'),
      overdue: sum('overdue'),
      avgRating: rated.length
        ? (rated.reduce((acc, row) => acc + row.avg_rating, 0) / rated.length).toFixed(2) : '—',
      avgResolution: timed.length
        ? hours(timed.reduce((acc, row) => acc + row.avg_resolution_hours, 0) / timed.length) : '—',
    };
  }, [rows]);

  if (performance.loading) return <LoadingBlock label="Loading officer performance…" />;
  if (performance.error) {
    return <ErrorState message={performance.error} onRetry={performance.reload} />;
  }

  const chartData = [...rows].filter((row) => row.assigned > 0)
    .sort((a, b) => b.open - a.open).slice(0, 8)
    .map((row) => ({
      name: row.officer.split(' ')[0], open: row.open,
      resolved: row.resolved, overdue: row.overdue,
    }));

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <StatCard label="Open" value={totals.open} tone="blue" />
        <StatCard label="Resolved" value={totals.resolved} tone="green" />
        <StatCard label="Past TAT" value={totals.overdue} tone="red" />
        <StatCard label="Average rating" value={totals.avgRating} tone="amber" icon={Star}
          hint={`Avg resolution ${totals.avgResolution}`} />

      </div>

      <Card>
        <CardHeader title="Workload" subtitle="Eight officers with the most open cases" />

        <div className="px-2 py-3">
          {chartData.length ? (
            <BarsChart data={chartData} xKey="name" height={240}
              series={[
                { key: 'open', name: 'Open', color: '#2563eb' },
                { key: 'resolved', name: 'Resolved', color: '#10b981' },
                { key: 'overdue', name: 'Overdue', color: '#dc2626' },
              ]} />
          ) : <p className="py-12 text-center text-xs text-slate-500">No assigned complaints yet</p>}
        </div>
      </Card>

      <Card>
        <CardHeader title="Scorecard" subtitle={`${rows.length} officers`} />

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 p-4">
          <Select value={departmentId} onChange={(e) => setDepartmentId(e.target.value)}>
            <option value="">All departments</option>
            {(departments.data || []).map((dept) => (
              <option key={dept.id} value={dept.id}>{dept.name}</option>
            ))}
          </Select>
          <Select value={level} onChange={(e) => setLevel(e.target.value)}>
            <option value="">Any level</option>
            {[1, 2, 3, 4].map((option) => <option key={option} value={option}>L{option}</option>)}
          </Select>
        </div>
        <DataTable
          rows={rows}
          pageSize={10}
          dense
          emptyTitle="No officers to report on"
          columns={[
            { key: 'officer', label: 'Officer', sortable: true,
              render: (row) => (
                <div>
                  <p className="text-xs font-semibold text-slate-800">{row.officer}</p>
                  <p className="text-[10px] text-slate-400">
                    {row.designation || 'Officer'}{row.active ? '' : ' · inactive'}
                  </p>
                </div>
              ) },
            { key: 'department', label: 'Department' },
            { key: 'level', label: 'Level', sortable: true,
              render: (row) => <LevelBadge level={row.level} /> },
            { key: 'assigned', label: 'Assigned', align: 'right', sortable: true },
            { key: 'resolved', label: 'Resolved', align: 'right', sortable: true },
            { key: 'open', label: 'Pending', align: 'right', sortable: true },
            { key: 'overdue', label: 'Overdue', align: 'right', sortable: true,
              render: (row) => (
                <span className={row.overdue ? 'text-xs font-semibold text-red-600' : 'text-xs'}>
                  {row.overdue}
                </span>
              ) },
            { key: 'avg_ack_hours', label: 'Ack time', align: 'right',
              render: (row) => <span className="text-xs">{hours(row.avg_ack_hours)}</span> },
            { key: 'avg_resolution_hours', label: 'Resolution time', align: 'right',
              render: (row) => <span className="text-xs">{hours(row.avg_resolution_hours)}</span> },
            { key: 'escalation_rate', label: 'Escalated', align: 'right', sortable: true,
              render: (row) => <span className="text-xs">{row.escalation_rate}%</span> },
            { key: 'avg_rating', label: 'Rating', align: 'right',
              render: (row) => (
                <span className="text-xs font-semibold text-amber-700">
                  {row.avg_rating ? `★ ${row.avg_rating} (${row.ratings_count})` : '—'}
                </span>
              ) },
          ]}
        />
      </Card>
    </div>
  );
}

