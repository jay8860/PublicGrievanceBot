import React, { useState } from 'react';
import { Download, FileSpreadsheet } from 'lucide-react';
import { BarsChart, MonthlyChart } from '../components/Charts';
import { Button, Field, Input, Select } from '../components/controls';
import { Card, CardHeader } from '../components/ui';
import { ErrorState, LoadingBlock } from '../components/feedback';
import { useToast } from '../components/Toast';
import { useFetch } from '../hooks/useFetch';
import { downloadBlob, hours } from '../lib/utils';
import { AnalyticsApi, DepartmentApi, ReportApi, apiErrorMessage } from '../services/apiV2';

export default function Reports() {
  const toast = useToast();
  const [departmentId, setDepartmentId] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [busy, setBusy] = useState('');

  const trends = useFetch(() => AnalyticsApi.trends(6), []);
  const wards = useFetch(() => AnalyticsApi.wards(), []);
  const overview = useFetch(() => AnalyticsApi.overview(), []);
  const departments = useFetch(() => DepartmentApi.list(), []);

  const exportReport = async (format) => {
    setBusy(format);
    try {
      const params = {};
      if (departmentId) params.department_id = departmentId;
      if (dateFrom) params.date_from = `${dateFrom}T00:00:00`;
      if (dateTo) params.date_to = `${dateTo}T23:59:59`;
      const blob = await ReportApi.exportComplaints(format, params);
      downloadBlob(blob, `grievance-report-${new Date().toISOString().slice(0, 10)}.${format}`);
      toast.push(`${format.toUpperCase()} export downloaded`, 'success');
    } catch (err) {
      toast.push(apiErrorMessage(err), 'error');
    } finally {
      setBusy('');
    }
  };

  if (trends.loading || overview.loading) return <LoadingBlock label="Building analytics…" />;
  if (trends.error) return <ErrorState message={trends.error} onRetry={trends.reload} />;

  const summary = overview.data || {};
  const wardRows = (wards.data || []).slice(0, 8);
  const deptRows = summary.departments || [];

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader title="Export"
          subtitle="CSV or Excel, filtered by department and dates" />

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 p-4 items-end">
          <Field label="Department">
            <Select value={departmentId} onChange={(e) => setDepartmentId(e.target.value)}>
              <option value="">All departments</option>
              {(departments.data || []).map((dept) => (
                <option key={dept.id} value={dept.id}>{dept.name}</option>
              ))}
            </Select>
          </Field>
          <Field label="From">
            <Input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
          </Field>
          <Field label="To">
            <Input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
          </Field>
          <div className="flex gap-2">
            <Button variant="secondary" loading={busy === 'csv'} onClick={() => exportReport('csv')}>
              <Download size={13} /> CSV
            </Button>
            <Button loading={busy === 'xlsx'} onClick={() => exportReport('xlsx')}>
              <FileSpreadsheet size={13} /> Excel
            </Button>
          </div>
        </div>
      </Card>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <Card className="px-4 py-3">
          <p className="text-[11px] text-slate-500">Total complaints</p>
          <p className="mt-1 text-[20px] font-semibold text-slate-900 tabular-nums">
            {summary.total ?? 0}
          </p>
        </Card>
        <Card className="px-4 py-3">
          <p className="text-[11px] text-slate-500">Resolution rate</p>
          <p className="mt-1 text-[20px] font-semibold text-emerald-700 tabular-nums">
            {summary.total ? `${Math.round(((summary.resolved || 0) / summary.total) * 100)}%` : '—'}
          </p>
        </Card>
        <Card className="px-4 py-3">
          <p className="text-[11px] text-slate-500">Average resolution time</p>
          <p className="mt-1 text-[20px] font-semibold text-slate-900 tabular-nums">
            {hours(summary.avg_resolution_hours)}
          </p>
        </Card>
        <Card className="px-4 py-3">
          <p className="text-[11px] text-slate-500">Escalation rate</p>
          <p className="mt-1 text-[20px] font-semibold text-amber-700 tabular-nums">
            {summary.total ? `${Math.round(((summary.escalated || 0) / summary.total) * 100)}%` : '—'}
          </p>
        </Card>

      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <Card>
          <CardHeader title="Monthly" subtitle="Received and resolved, six months" />

          <div className="px-2 py-3"><MonthlyChart data={trends.data || []} /></div>
        </Card>
        <Card>
          <CardHeader title="By ward" subtitle="Eight wards with the most complaints" />

          <div className="px-2 py-3">
            {wardRows.length ? (
              <BarsChart data={wardRows} xKey="ward" layout="vertical" height={280}
                series={[{ key: 'total', name: 'Complaints', color: '#1e3a8a' }]} />
            ) : <p className="py-16 text-center text-xs text-slate-500">No ward data yet</p>}
          </div>
        </Card>
      </div>

      <Card>
        <CardHeader title="By department"
          subtitle="Open, resolved, past TAT and average time" />

        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead className="bg-slate-50 text-[11px] font-medium text-slate-500">
              <tr>
                <th className="px-4 py-2 text-left">Department</th>
                <th className="px-4 py-2 text-right">Total</th>
                <th className="px-4 py-2 text-right">Open</th>
                <th className="px-4 py-2 text-right">Resolved</th>
                <th className="px-4 py-2 text-right">Escalated</th>
                <th className="px-4 py-2 text-right">Overdue</th>
                <th className="px-4 py-2 text-right">Avg resolution</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {deptRows.map((row) => (
                <tr key={row.department_id}>
                  <td className="px-4 py-2 text-xs font-medium text-slate-800">{row.department}</td>
                  <td className="px-4 py-2 text-right text-xs">{row.total}</td>
                  <td className="px-4 py-2 text-right text-xs">{row.open}</td>
                  <td className="px-4 py-2 text-right text-xs">{row.resolved}</td>
                  <td className="px-4 py-2 text-right text-xs">{row.escalated}</td>
                  <td className="px-4 py-2 text-right text-xs text-red-600">{row.overdue}</td>
                  <td className="px-4 py-2 text-right text-xs">
                    {hours(row.avg_resolution_hours)}
                  </td>
                </tr>
              ))}
              {deptRows.length === 0 && (
                <tr>
                  <td colSpan={7} className="px-4 py-8 text-center text-xs text-slate-500">
                    No department data yet
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}

