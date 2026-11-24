import React, { useMemo, useState } from 'react';
import { Pencil, Settings2, Users } from 'lucide-react';
import { Button, Field, Input, Textarea } from '../components/controls';
import { Modal } from '../components/overlays';
import { Card, CardHeader, cls } from '../components/ui';
import { ErrorState, LoadingBlock } from '../components/feedback';
import { useToast } from '../components/Toast';
import { useFetch } from '../hooks/useFetch';
import { AnalyticsApi, DepartmentApi, OfficerApi, RuleApi, apiErrorMessage } from '../services/apiV2';

const DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

export default function Departments({ onNavigate }) {
  const toast = useToast();
  const [editing, setEditing] = useState(null);
  const [categoriesFor, setCategoriesFor] = useState(null);
  const [tatFor, setTatFor] = useState(null);
  const [officersFor, setOfficersFor] = useState(null);
  const [busy, setBusy] = useState('');
  const [newCategory, setNewCategory] = useState({ name: '', ai_label: '' });
  const [tatForm, setTatForm] = useState(null);

  const departments = useFetch(() => DepartmentApi.list(), []);
  const rules = useFetch(() => RuleApi.list(), []);
  const officers = useFetch(() => OfficerApi.list({}), []);
  const overview = useFetch(() => AnalyticsApi.dashboard(30), []);
  const categories = useFetch(
    () => (categoriesFor ? DepartmentApi.categories(categoriesFor.id) : Promise.resolve([])),
    [categoriesFor?.id]
  );

  const performance = useMemo(() => {
    const map = {};
    (overview.data?.departments || []).forEach((row) => { map[row.department_id] = row; });
    return map;
  }, [overview.data]);

  const openTat = (dept) => {
    const rule = (rules.data || []).find((row) => row.department_id === dept.id && !row.category_id);
    setTatFor(dept);
    setTatForm({
      ack_hours: rule?.ack_hours ?? 12, action_hours: rule?.action_hours ?? 24,
      l1_hours: rule?.l1_hours ?? 48, l2_hours: rule?.l2_hours ?? 24,
      l3_hours: rule?.l3_hours ?? 24, l4_hours: rule?.l4_hours ?? 48,
      reminder_hours: rule?.reminder_hours ?? 6,
      working_days: rule?.working_days ?? [0, 1, 2, 3, 4, 5],
      holidays: (rule?.holidays || []).join(', '),
    });
  };

  const saveDepartment = async () => {
    setBusy('dept');
    try {
      await DepartmentApi.update(editing.id, {
        code: editing.code, name: editing.name,
        description: editing.description || '', active: Boolean(editing.active),
      });
      toast.push('Department updated', 'success');
      setEditing(null);
      departments.reload();
    } catch (err) { toast.push(apiErrorMessage(err), 'error'); }
    finally { setBusy(''); }
  };

  const saveTat = async () => {
    setBusy('tat');
    try {
      await RuleApi.upsert(tatFor.id, {
        ...tatForm,
        working_days: tatForm.working_days.map(Number),
        holidays: String(tatForm.holidays || '').split(',').map((s) => s.trim()).filter(Boolean),
      });
      toast.push('TAT policy saved', 'success');
      setTatFor(null);
      rules.reload();
    } catch (err) { toast.push(apiErrorMessage(err), 'error'); }
    finally { setBusy(''); }
  };

  const addCategory = async () => {
    if (!newCategory.name.trim()) { toast.push('Category name is required', 'error'); return; }
    setBusy('category');
    try {
      await DepartmentApi.createCategory({
        department_id: categoriesFor.id,
        name: newCategory.name.trim(),
        ai_label: newCategory.ai_label.trim() || newCategory.name.trim(),
        active: true,
      });
      toast.push('Category added', 'success');
      setNewCategory({ name: '', ai_label: '' });
      categories.reload();
      departments.reload();
    } catch (err) { toast.push(apiErrorMessage(err), 'error'); }
    finally { setBusy(''); }
  };

  if (departments.loading) return <LoadingBlock label="Loading departments…" />;
  if (departments.error) return <ErrorState message={departments.error} onRetry={departments.reload} />;

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {(departments.data || []).map((dept) => {
          const perf = performance[dept.id] || {};
          const deptOfficers = (officers.data || []).filter((officer) => officer.department_id === dept.id);
          const rule = (rules.data || []).find((row) => row.department_id === dept.id && !row.category_id);
          return (
            <Card key={dept.id}>
              <CardHeader title={dept.name} subtitle={`${dept.code} · ${dept.categories} categories`}
                actions={<span className={dept.active
                  ? 'text-[11px] font-semibold text-emerald-700'
                  : 'text-[11px] font-semibold text-red-600'}>
                  {dept.active ? 'Active' : 'Inactive'}
                </span>} />
              <div className="p-4 space-y-3">
                <p className="text-xs text-slate-500 min-h-[32px]">
                  {dept.description || 'No description'}
                </p>
                <div className="grid grid-cols-4 gap-2 py-1">
                  {[
                    ['Total', perf.total ?? 0],
                    ['Open', perf.open ?? 0],
                    ['Resolved', perf.resolved ?? 0],
                    ['Past TAT', perf.overdue ?? 0],
                  ].map(([label, value]) => (
                    <div key={label}>
                      <p className="text-[11px] text-slate-500">{label}</p>
                      <p className={cls('text-[15px] font-semibold tabular-nums',
                        label === 'Past TAT' && value > 0 ? 'text-red-700' : 'text-slate-900')}>
                        {value}
                      </p>
                    </div>
                  ))}
                </div>

                <p className="text-[11px] text-slate-500">
                  {deptOfficers.length} officers · TAT L1 {rule?.l1_hours ?? 48}h → L4 {rule?.l4_hours ?? 48}h
                </p>
                <div className="flex flex-wrap gap-1.5 pt-1">
                  <Button size="sm" variant="secondary" onClick={() => setEditing({ ...dept })}>
                    <Pencil size={12} /> Edit
                  </Button>
                  <Button size="sm" variant="secondary" onClick={() => setCategoriesFor(dept)}>
                    <ClipboardList size={12} /> Categories
                  </Button>
                  <Button size="sm" variant="secondary" onClick={() => openTat(dept)}>
                    <Settings2 size={12} /> TAT
                  </Button>
                  <Button size="sm" variant="secondary" onClick={() => setOfficersFor(dept)}>
                    <Users size={12} /> Officers
                  </Button>
                </div>
              </div>
            </Card>
          );
        })}
      </div>

      <Modal open={Boolean(editing)} onClose={() => setEditing(null)} title="Edit department"
        footer={(
          <>
            <Button variant="secondary" onClick={() => setEditing(null)}>Cancel</Button>
            <Button loading={busy === 'dept'} onClick={saveDepartment}>Save changes</Button>
          </>
        )}>
        {editing && (
          <div className="space-y-3">
            <Field label="Code"><Input value={editing.code} disabled /></Field>
            <Field label="Name" required>
              <Input value={editing.name}
                onChange={(e) => setEditing({ ...editing, name: e.target.value })} />
            </Field>
            <Field label="Description">
              <Textarea value={editing.description || ''}
                onChange={(e) => setEditing({ ...editing, description: e.target.value })} />
            </Field>
            <label className="flex items-center gap-2 text-sm text-slate-700">
              <input type="checkbox" checked={Boolean(editing.active)}
                onChange={(e) => setEditing({ ...editing, active: e.target.checked })}
                className="h-4 w-4 rounded border-slate-300 text-blue-700" />
              Department is active
            </label>
          </div>
        )}
      </Modal>

      <Modal open={Boolean(categoriesFor)} onClose={() => setCategoriesFor(null)}
        title={`Categories · ${categoriesFor?.name || ''}`}
        subtitle="The AI label is what the vision model returns; the name is shown to staff."
        width="max-w-3xl"
        footer={<Button variant="secondary" onClick={() => setCategoriesFor(null)}>Close</Button>}>
        <div className="space-y-4">
          {categories.loading && <LoadingBlock label="Loading categories…" />}
          {categories.error && <ErrorState message={categories.error} onRetry={categories.reload} />}
          <div className="divide-y divide-slate-100 rounded-lg border border-slate-200">
            {(categories.data || []).map((category) => (
              <div key={category.id} className="flex items-center justify-between gap-3 px-3 py-2">
                <div>
                  <p className="text-sm font-medium text-slate-800">{category.name}</p>
                  <p className="text-[11px] text-slate-500">AI label: {category.ai_label || '—'}</p>
                </div>
                <span className={category.active ? 'text-[11px] font-semibold text-emerald-700'
                  : 'text-[11px] font-semibold text-red-600'}>
                  {category.active ? 'Active' : 'Inactive'}
                </span>
              </div>
            ))}
            {(categories.data || []).length === 0 && !categories.loading && (
              <p className="px-3 py-4 text-xs text-slate-500">No categories yet.</p>
            )}
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 items-end">
            <Field label="New category">
              <Input value={newCategory.name} placeholder="e.g. Drainage"
                onChange={(e) => setNewCategory({ ...newCategory, name: e.target.value })} />
            </Field>
            <Field label="AI label">
              <Input value={newCategory.ai_label} placeholder="e.g. Drainage"
                onChange={(e) => setNewCategory({ ...newCategory, ai_label: e.target.value })} />
            </Field>
            <Button loading={busy === 'category'} onClick={addCategory}>Add category</Button>
          </div>
        </div>
      </Modal>

      <Modal open={Boolean(tatFor)} onClose={() => setTatFor(null)}
        title={`TAT policy · ${tatFor?.name || ''}`}
        subtitle="Hours are counted from the moment a complaint reaches each level."
        footer={(
          <>
            <Button variant="secondary" onClick={() => setTatFor(null)}>Cancel</Button>
            <Button loading={busy === 'tat'} onClick={saveTat}>Save TAT policy</Button>
          </>
        )}>
        {tatForm && (
          <div className="space-y-4">
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
              {[
                ['ack_hours', 'L1 acknowledge'], ['action_hours', 'First action'],
                ['l1_hours', 'L1 resolution'], ['l2_hours', 'L2 window'],
                ['l3_hours', 'L3 window'], ['l4_hours', 'L4 window'],
                ['reminder_hours', 'Reminder before due'],
              ].map(([key, label]) => (
                <Field key={key} label={label}>
                  <Input type="number" min="1" max="720" value={tatForm[key]}
                    onChange={(e) => setTatForm({ ...tatForm, [key]: e.target.value })} />
                </Field>
              ))}
            </div>
            <div>
              <p className="text-xs font-semibold text-slate-600 mb-1">Working days</p>
              <div className="flex flex-wrap gap-2">
                {DAYS.map((day, index) => (
                  <label key={day}
                    className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 px-2 py-1 text-xs">
                    <input type="checkbox" checked={tatForm.working_days.map(Number).includes(index)}
                      onChange={(e) => {
                        const current = new Set(tatForm.working_days.map(Number));
                        if (e.target.checked) current.add(index); else current.delete(index);
                        setTatForm({ ...tatForm, working_days: [...current].sort() });
                      }}
                      className="h-3.5 w-3.5 rounded border-slate-300 text-blue-700" />
                    {day}
                  </label>
                ))}
              </div>
            </div>
            <Field label="Holiday calendar" hint="Comma-separated ISO dates, e.g. 2026-01-26, 2026-03-25">
              <Input value={tatForm.holidays}
                onChange={(e) => setTatForm({ ...tatForm, holidays: e.target.value })} />
            </Field>
          </div>
        )}
      </Modal>

      <Modal open={Boolean(officersFor)} onClose={() => setOfficersFor(null)}
        title={`Officers · ${officersFor?.name || ''}`} width="max-w-2xl"
        footer={<Button variant="secondary" onClick={() => setOfficersFor(null)}>Close</Button>}>
        <div className="divide-y divide-slate-100 rounded-lg border border-slate-200">
          {(officers.data || [])
            .filter((officer) => officer.department_id === officersFor?.id)
            .map((officer) => (
              <div key={officer.id} className="flex items-center justify-between gap-3 px-3 py-2">
                <div>
                  <p className="text-sm font-medium text-slate-800">{officer.full_name}</p>
                  <p className="text-[11px] text-slate-500">
                    {officer.designation || 'Officer'} · L{officer.level} ·{' '}
                    {officer.jurisdiction_value || officer.jurisdiction_type}
                  </p>
                </div>
                <span className="text-[11px] font-semibold text-slate-500">
                  {officer.telegram_connected ? 'Telegram connected' : 'No Telegram'}
                </span>
              </div>
            ))}
        </div>
        {onNavigate && (
          <Button className="mt-3" size="sm" variant="secondary" onClick={() => onNavigate('officers')}>
            Open officer management
          </Button>
        )}
      </Modal>
    </div>
  );
}



