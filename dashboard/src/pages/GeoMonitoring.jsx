import React, { useMemo, useState } from 'react';
import { Flame, MapPin, RefreshCcw } from 'lucide-react';
import ComplaintDrawer from '../components/ComplaintDrawer';
import ComplaintMap from '../components/ComplaintMap';
import { Button, Select } from '../components/controls';
import { Card, CardHeader } from '../components/ui';
import { ErrorState, LoadingBlock } from '../components/feedback';
import { useFetch } from '../hooks/useFetch';
import { AnalyticsApi, DepartmentApi } from '../services/apiV2';

export default function GeoMonitoring({ token }) {
  const [departmentId, setDepartmentId] = useState('');
  const [severity, setSeverity] = useState('');
  const [status, setStatus] = useState('');
  const [level, setLevel] = useState('');
  const [mode, setMode] = useState('pins');
  const [selected, setSelected] = useState(null);

  const departments = useFetch(() => DepartmentApi.list(), []);
  const wards = useFetch(() => AnalyticsApi.wards(), []);

  const params = useMemo(() => {
    const query = {};
    if (departmentId) query.department_id = departmentId;
    if (severity) query.severity = severity;
    if (status) query.status = status;
    if (level) query.level = Number(level);
    return query;
  }, [departmentId, severity, status, level]);

  const geo = useFetch(() => AnalyticsApi.geo(params), [JSON.stringify(params)]);

  if (geo.loading && !geo.data) return <LoadingBlock label="Loading complaint map…" />;
  if (geo.error) return <ErrorState message={geo.error} onRetry={geo.reload} />;

  const points = geo.data?.points || [];
  const overdue = points.filter((point) => point.overdue).length;

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader title="Filters" subtitle="Narrow what the map shows"
          actions={(
            <Button size="sm" variant="secondary" onClick={geo.reload}>
              <RefreshCcw size={12} /> Refresh
            </Button>
          )} />
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 p-4">
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
          <Select value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="">Any status</option>
            {['NEW', 'ASSIGNED', 'ACKNOWLEDGED', 'IN_PROGRESS', 'ESCALATED', 'RESOLVED', 'CLOSED', 'REOPENED'].map((option) => (
              <option key={option} value={option}>{option.replace(/_/g, ' ')}</option>
            ))}
          </Select>
          <Select value={level} onChange={(e) => setLevel(e.target.value)}>
            <option value="">Any level</option>
            {[1, 2, 3, 4].map((option) => (
              <option key={option} value={option}>Level {option}</option>
            ))}
          </Select>
        </div>
      </Card>

      <div className="grid grid-cols-1 xl:grid-cols-4 gap-4">
        <Card className="xl:col-span-3">
          <CardHeader title="Complaint map"
            subtitle={mode === 'pins'
              ? 'One pin per complaint, coloured by priority'
              : 'Darker areas hold more complaints'}
            actions={(
              <div className="flex flex-wrap gap-2">
                <Button size="sm" variant={mode === 'pins' ? 'navy' : 'secondary'}
                  onClick={() => setMode('pins')}>
                  <MapPin size={12} /> Pins
                </Button>
                <Button size="sm" variant={mode === 'heat' ? 'navy' : 'secondary'}
                  onClick={() => setMode('heat')}>
                  <Flame size={12} /> Heat
                </Button>
              </div>
            )} />
          <div className="p-3">
            {points.length === 0 ? (
              <div className="flex h-[520px] flex-col items-center justify-center gap-2 rounded-md border border-dashed border-slate-300 text-slate-400">
                <MapPin size={24} />
                <p className="text-[12px] text-slate-600">No complaints carry coordinates</p>
                <p className="text-[11px]">Location is captured through the Telegram bot.</p>
              </div>

            ) : (
              <ComplaintMap points={points} onSelect={setSelected} height={520} mode={mode} />
            )}
          </div>
          <div className="flex flex-wrap items-center gap-4 px-3 pb-3 text-[11px] text-slate-500">
            <span className="font-medium text-slate-600">
              {points.length} plotted · {overdue} past TAT
            </span>
            {mode === 'pins' ? (
              <>
                <span className="flex items-center gap-1.5">
                  <span className="h-2.5 w-2.5 rounded-full" style={{ background: '#9d5145' }} /> High
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="h-2.5 w-2.5 rounded-full" style={{ background: '#967a3d' }} /> Medium
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="h-2.5 w-2.5 rounded-full" style={{ background: '#557059' }} /> Low
                </span>
                <span>Pin colour is the priority. Click a pin for the complaint.</span>
              </>
            ) : (
              <>
                <span className="flex items-center gap-1.5">
                  <span className="h-2.5 w-2.5 rounded-full" style={{ background: '#b89a58' }} /> 1 report
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="h-2.5 w-2.5 rounded-full" style={{ background: '#9d6347' }} /> 2–3
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="h-2.5 w-2.5 rounded-full" style={{ background: '#7f3f36' }} /> 4 or more
                </span>
                <span>Darker means more complaints in the same area.</span>
              </>
            )}
          </div>
        </Card>

        <Card>
          <CardHeader title="By ward" subtitle="Complaints per ward" />

          <ul className="divide-y divide-slate-100 max-h-[540px] overflow-y-auto">
            {(wards.data || []).length === 0 && (
              <li className="px-4 py-8 text-center text-xs text-slate-500">No ward data yet</li>
            )}
            {(wards.data || []).map((row) => (
              <li key={row.ward} className="px-4 py-2.5">
                <div className="flex items-center justify-between">
                  <p className="text-xs font-semibold text-slate-800">{row.ward}</p>
                  <span className="text-[11px] font-bold text-slate-700">{row.total}</span>
                </div>
                <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-slate-100">
                  <div className="h-full rounded-full bg-blue-600"
                    style={{ width: `${Math.min(100, (row.total / Math.max(1, (wards.data?.[0]?.total || 1))) * 100)}%` }} />
                </div>
                <p className="mt-1 text-[10px] text-slate-500">
                  {row.open} open · {row.resolved} resolved · {row.overdue} overdue
                </p>
              </li>
            ))}
          </ul>
        </Card>
      </div>

      <ComplaintDrawer complaintId={selected} token={token} onClose={() => setSelected(null)}
        onChanged={geo.reload} />
    </div>
  );
}
