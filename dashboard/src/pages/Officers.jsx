import React, { useEffect, useMemo, useState } from 'react';
import { Copy, KeyRound, Pencil, Plus, RefreshCcw, ShieldOff, UserCheck, UserX } from 'lucide-react';
import DataTable from '../components/DataTable';
import { Button, Field, Input, SearchInput, Select } from '../components/controls';
import { ConfirmDialog, Modal } from '../components/overlays';
import { Card, CardHeader, LevelBadge, TelegramBadge } from '../components/ui';
import { ErrorState, InlineAlert, LoadingBlock } from '../components/feedback';
import { useToast } from '../components/Toast';
import { useFetch } from '../hooks/useFetch';
import { DepartmentApi, OfficerApi, apiErrorMessage } from '../services/apiV2';

const LEVELS = [1, 2, 3, 4];
const SCOPES = ['district', 'block', 'ward', 'village'];

const EMPTY_FORM = {
  full_name: '', designation: '', department_id: '', level: 1, employee_code: '',
  mobile: '', email: '', jurisdiction_type: 'ward', jurisdiction_value: '',
  reports_to_id: '', available: true, active: true,
};

function OfficerForm({ open, initial, departments, peers, busy, onClose, onSave }) {
  const [form, setForm] = useState(EMPTY_FORM);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!open) return;
    setForm(initial ? {
      full_name: initial.full_name || '', designation: initial.designation || '',
      department_id: initial.department_id || '', level: initial.level || 1,
      employee_code: initial.employee_code || '', mobile: initial.mobile || '',
      email: initial.email || '', jurisdiction_type: initial.jurisdiction_type || 'ward',
      jurisdiction_value: initial.jurisdiction_value || '',
      reports_to_id: initial.reports_to_id || '',
      available: initial.available ?? true, active: initial.active ?? true,
    } : EMPTY_FORM);
    setError('');
  }, [open, initial]);

  const set = (patch) => setForm((current) => ({ ...current, ...patch }));
  const sameDepartment = peers.filter((officer) =>
    !form.department_id || officer.department_id === form.department_id);

  const submit = () => {
    if (form.full_name.trim().length < 2) { setError('Full name is required'); return; }
    if (!form.department_id) { setError('Select a department'); return; }
    setError('');
    onSave({ ...form, level: Number(form.level),
      reports_to_id: form.reports_to_id || null,
      jurisdiction_value: form.jurisdiction_value.trim() });
  };

  return (
    <Modal open={open} onClose={onClose} width="max-w-3xl"
      title={initial ? 'Edit officer' : 'Add officer'}
      subtitle="Jurisdiction decides which complaints this officer receives."
      footer={(
        <>
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button loading={busy} onClick={submit}>{initial ? 'Save changes' : 'Create officer'}</Button>
        </>
      )}>
      <div className="space-y-3">
        {error && <InlineAlert tone="danger">{error}</InlineAlert>}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <Field label="Full name" required>
            <Input value={form.full_name} onChange={(e) => set({ full_name: e.target.value })}
              placeholder="e.g. Rakesh Verma" />
          </Field>
          <Field label="Designation">
            <Input value={form.designation} onChange={(e) => set({ designation: e.target.value })}
              placeholder="e.g. Junior Engineer" />
          </Field>
          <Field label="Department" required>
            <Select value={form.department_id}
              onChange={(e) => set({ department_id: e.target.value, reports_to_id: '' })}>
              <option value="">Select department…</option>
              {departments.map((dept) => (
                <option key={dept.id} value={dept.id}>{dept.name}</option>
              ))}
            </Select>
          </Field>
          <Field label="Officer level" required hint="L1 handles complaints; L2–L4 receive escalations.">
            <Select value={form.level} onChange={(e) => set({ level: Number(e.target.value) })}>
              {LEVELS.map((level) => <option key={level} value={level}>L{level}</option>)}
            </Select>
          </Field>
          <Field label="Employee code">
            <Input value={form.employee_code} onChange={(e) => set({ employee_code: e.target.value })}
              placeholder="e.g. PWD-1042" />
          </Field>
          <Field label="Official mobile">
            <Input value={form.mobile} onChange={(e) => set({ mobile: e.target.value })}
              placeholder="10-digit number" />
          </Field>
          <Field label="Official email">
            <Input type="email" value={form.email} onChange={(e) => set({ email: e.target.value })}
              placeholder="name@dhamtari.gov.in" />
          </Field>
          <Field label="Reports to (escalation target)">
            <Select value={form.reports_to_id}
              onChange={(e) => set({ reports_to_id: e.target.value })}>
              <option value="">Not set</option>
              {sameDepartment.map((officer) => (
                <option key={officer.id} value={officer.id}>
                  {officer.full_name} (L{officer.level})
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Jurisdiction type">
            <Select value={form.jurisdiction_type}
              onChange={(e) => set({ jurisdiction_type: e.target.value })}>
              {SCOPES.map((scope) => <option key={scope} value={scope}>{scope}</option>)}
            </Select>
          </Field>
          <Field label="Jurisdiction value" hint="Ward / block / village name, or 'District' for L3–L4.">
            <Input value={form.jurisdiction_value}
              onChange={(e) => set({ jurisdiction_value: e.target.value })}
              placeholder="e.g. Ward 5" />
          </Field>
        </div>
        <div className="flex flex-wrap gap-4 pt-1">
          <label className="flex items-center gap-2 text-sm text-slate-700">
            <input type="checkbox" checked={form.available}
              onChange={(e) => set({ available: e.target.checked })}
              className="h-4 w-4 rounded border-slate-300 text-blue-700" />
            Available for new complaints
          </label>
          <label className="flex items-center gap-2 text-sm text-slate-700">
            <input type="checkbox" checked={form.active}
              onChange={(e) => set({ active: e.target.checked })}
              className="h-4 w-4 rounded border-slate-300 text-blue-700" />
            Account active
          </label>
        </div>
        <p className="text-[11px] text-slate-500">
          TAT hours are configured per department (Departments → TAT) so they stay consistent for
          every officer in that department.
        </p>
      </div>
    </Modal>
  );
}

function telegramStatus(officer) {
  if (officer.telegram_connected) return 'connected';
  if (officer.telegram_linked_at) return 'revoked';
  return 'none';
}

export default function Officers({ onNavigate }) {
  const toast = useToast();
  const [tab, setTab] = useState('table');
  const [search, setSearch] = useState('');
  const [departmentId, setDepartmentId] = useState('');
  const [level, setLevel] = useState('');
  const [status, setStatus] = useState('');
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [busy, setBusy] = useState('');
  const [inviteFor, setInviteFor] = useState(null);
  const [invitation, setInvitation] = useState(null);
  const [inviteTtl, setInviteTtl] = useState(48);
  const [pendingInvites, setPendingInvites] = useState([]);
  const [confirm, setConfirm] = useState(null);

  const officers = useFetch(() => OfficerApi.list({}), []);
  const departments = useFetch(() => DepartmentApi.list(), []);

  const rows = useMemo(() => {
    let list = officers.data || [];
    if (search.trim()) {
      const needle = search.trim().toLowerCase();
      list = list.filter((officer) =>
        officer.full_name.toLowerCase().includes(needle)
        || (officer.employee_code || '').toLowerCase().includes(needle)
        || (officer.designation || '').toLowerCase().includes(needle));
    }
    if (departmentId) list = list.filter((officer) => officer.department_id === departmentId);
    if (level) list = list.filter((officer) => officer.level === Number(level));
    if (status === 'active') list = list.filter((officer) => officer.active);
    if (status === 'inactive') list = list.filter((officer) => !officer.active);
    if (status === 'connected') list = list.filter((officer) => officer.telegram_connected);
    if (status === 'not_connected') list = list.filter((officer) => !officer.telegram_connected);
    return list;
  }, [officers.data, search, departmentId, level, status]);

  const saveOfficer = async (payload) => {
    setBusy('form');
    try {
      if (editing) {
        await OfficerApi.update(editing.id, payload);
        toast.push('Officer updated', 'success');
        setFormOpen(false);
        setEditing(null);
      } else {
        const created = await OfficerApi.create(payload);
        toast.push('Officer created - generate a Telegram invitation next', 'success');
        setFormOpen(false);
        setInviteFor(created);
        setInvitation(null);
      }
      officers.reload();
    } catch (err) {
      toast.push(apiErrorMessage(err), 'error');
    } finally {
      setBusy('');
    }
  };

  const createInvitation = async () => {
    if (!inviteFor) return;
    setBusy('invite');
    try {
      const data = await OfficerApi.invite(inviteFor.id, Number(inviteTtl));
      setInvitation(data);
      setPendingInvites((current) => [...new Set([...current, inviteFor.id])]);
      toast.push('Invitation code generated', 'success');
    } catch (err) {
      toast.push(apiErrorMessage(err), 'error');
    } finally {
      setBusy('');
    }
  };

  const copyCode = async (code) => {
    try {
      await navigator.clipboard.writeText(code);
      toast.push('Code copied to clipboard', 'success');
    } catch {
      toast.push('Copy failed - select the code manually', 'error');
    }
  };

  const act = async (label, action, message) => {
    setBusy(label);
    try {
      await action();
      toast.push(message, 'success');
      officers.reload();
    } catch (err) {
      toast.push(apiErrorMessage(err), 'error');
    } finally {
      setBusy('');
      setConfirm(null);
    }
  };

  if (officers.loading || departments.loading) return <LoadingBlock label="Loading officers…" />;
  if (officers.error) return <ErrorState message={officers.error} onRetry={officers.reload} />;

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader title="Officers" subtitle={`${rows.length} shown`}
          actions={(
            <div className="flex flex-wrap gap-2">
              <Button size="sm" variant="secondary" onClick={officers.reload}>
                <RefreshCcw size={13} />
              </Button>
              <Button size="sm" onClick={() => { setEditing(null); setFormOpen(true); }}>
                <Plus size={13} /> Add officer
              </Button>
            </div>
          )} />
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 p-4">
          <SearchInput value={search} onChange={setSearch} placeholder="Name, code or designation…" />
          <Select value={departmentId} onChange={(e) => setDepartmentId(e.target.value)}>
            <option value="">All departments</option>
            {(departments.data || []).map((dept) => (
              <option key={dept.id} value={dept.id}>{dept.name}</option>
            ))}
          </Select>
          <div className="flex gap-2">
            <Select value={level} onChange={(e) => setLevel(e.target.value)}>
              <option value="">Any level</option>
              {LEVELS.map((value) => <option key={value} value={value}>L{value}</option>)}
            </Select>
            <Select value={status} onChange={(e) => setStatus(e.target.value)}>
              <option value="">Any status</option>
              <option value="active">Active</option>
              <option value="inactive">Inactive</option>
              <option value="connected">Telegram connected</option>
              <option value="not_connected">Telegram missing</option>
            </Select>
          </div>
        </div>
        <div className="px-4 pb-3 flex gap-2">
          <Button size="sm" variant={tab === 'table' ? 'navy' : 'secondary'}
            onClick={() => setTab('table')}>Officer list</Button>
          <Button size="sm" variant={tab === 'hierarchy' ? 'navy' : 'secondary'}
            onClick={() => setTab('hierarchy')}>L1–L4 hierarchy</Button>
        </div>
      </Card>

      {tab === 'table' ? (
        <Card>
          <DataTable
            rows={rows}
            pageSize={12}
            dense
            emptyTitle="No officers match"
            emptyMessage="Add an officer to start routing complaints."

            columns={[
              { key: 'employee_code', label: 'Officer ID',
                render: (row) => <span className="text-[11px] font-semibold text-slate-600">
                  {row.employee_code || row.id.slice(0, 8)}
                </span> },
              { key: 'full_name', label: 'Name', sortable: true,
                render: (row) => (
                  <div>
                    <p className="text-xs font-semibold text-slate-800">{row.full_name}</p>
                    <p className="text-[10px] text-slate-400">{row.designation || 'Officer'}</p>
                  </div>
                ) },
              { key: 'department', label: 'Department' },
              { key: 'level', label: 'Level', sortable: true,
                render: (row) => <LevelBadge level={row.level} /> },
              { key: 'jurisdiction', label: 'Jurisdiction',
                render: (row) => (
                  <span className="text-[11px] text-slate-600">
                    {row.jurisdiction_value || row.jurisdiction_type}
                  </span>
                ) },
              { key: 'telegram', label: 'Telegram',
                render: (row) => (
                  <TelegramBadge status={pendingInvites.includes(row.id) && !row.telegram_connected
                    ? 'pending' : telegramStatus(row)} />
                ) },
              { key: 'open_complaints', label: 'Pending', align: 'right', sortable: true },
              { key: 'active', label: 'Status',
                render: (row) => (
                  <span className={row.active ? 'text-[11px] font-semibold text-emerald-700'
                    : 'text-[11px] font-semibold text-red-600'}>
                    {row.active ? 'Active' : 'Inactive'}
                  </span>
                ) },
              { key: 'actions', label: 'Actions', align: 'right',
                render: (row) => (
                  <div className="flex justify-end gap-1.5">
                    <button title="Edit" onClick={() => { setEditing(row); setFormOpen(true); }}
                      className="p-1.5 rounded text-slate-500 hover:bg-slate-100">
                      <Pencil size={13} />
                    </button>
                    <button title="Generate Telegram invitation"
                      onClick={() => { setInviteFor(row); setInvitation(null); }}
                      className="p-1.5 rounded text-blue-700 hover:bg-blue-50">
                      <KeyRound size={13} />
                    </button>
                    {row.telegram_connected && (
                      <button title="Revoke Telegram access"
                        onClick={() => setConfirm({
                          title: 'Revoke Telegram access?',
                          message: `${row.full_name} will stop receiving assignments until a new invitation is redeemed.`,
                          label: 'Revoke', tone: 'danger',
                          action: () => act('revoke', () => OfficerApi.revokeTelegram(row.id),
                            'Telegram access revoked'),
                        })}
                        className="p-1.5 rounded text-amber-600 hover:bg-amber-50">
                        <ShieldOff size={13} />
                      </button>
                    )}
                    <button title={row.active ? 'Deactivate' : 'Activate'}
                      onClick={() => setConfirm({
                        title: row.active ? 'Deactivate officer?' : 'Activate officer?',
                        message: row.active
                          ? `${row.full_name} will no longer receive new complaints.`
                          : `${row.full_name} will be available for routing again.`,
                        label: row.active ? 'Deactivate' : 'Activate',
                        tone: row.active ? 'danger' : 'primary',
                        action: () => act('toggle',
                          () => OfficerApi.update(row.id, { active: !row.active }),
                          row.active ? 'Officer deactivated' : 'Officer activated'),
                      })}
                      className={row.active ? 'p-1.5 rounded text-red-600 hover:bg-red-50'
                        : 'p-1.5 rounded text-emerald-600 hover:bg-emerald-50'}>
                      {row.active ? <UserX size={13} /> : <UserCheck size={13} />}
                    </button>
                  </div>
                ) },
            ]}
          />
        </Card>
      ) : (
        <div className="space-y-4">
          {(departments.data || []).map((dept) => {
            const deptOfficers = (officers.data || []).filter((officer) =>
              officer.department_id === dept.id);
            if (deptOfficers.length === 0) return null;
            return (
              <Card key={dept.id}>
                <CardHeader title={dept.name} subtitle={`${deptOfficers.length} officers`} />
                <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-3 p-4">
                  {LEVELS.map((levelValue) => {
                    const levelOfficers = deptOfficers.filter((officer) =>
                      officer.level === levelValue);
                    return (
                      <div key={levelValue}
                        className="rounded-lg border border-slate-200 bg-slate-50/60 p-2">
                        <p className="mb-2 flex items-center gap-1.5 text-[11px] text-slate-500">
                          <LevelBadge level={levelValue} /> Level {levelValue}
                        </p>
                        <div className="space-y-1.5">
                          {levelOfficers.map((officer) => (
                            <div key={officer.id}
                              className="rounded-md bg-white border border-slate-200 px-2 py-1.5">
                              <p className="text-xs font-semibold text-slate-800">
                                {officer.full_name}
                              </p>
                              <p className="text-[10px] text-slate-500">
                                {officer.jurisdiction_value || officer.jurisdiction_type}
                                {' · '}{officer.open_complaints} pending
                              </p>
                              <div className="mt-1">
                                <TelegramBadge status={pendingInvites.includes(officer.id)
                                  && !officer.telegram_connected ? 'pending'
                                  : telegramStatus(officer)} />
                              </div>
                            </div>
                          ))}
                          {levelOfficers.length === 0 && (
                            <p className="text-[10px] text-slate-400">No officer configured</p>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </Card>
            );
          })}
        </div>
      )}

      <OfficerForm open={formOpen} initial={editing} departments={departments.data || []}
        peers={officers.data || []} busy={busy === 'form'}
        onClose={() => { setFormOpen(false); setEditing(null); }}
        onSave={saveOfficer} />

      <Modal open={Boolean(inviteFor)} onClose={() => { setInviteFor(null); setInvitation(null); }}
        title={`Telegram onboarding · ${inviteFor?.full_name || ''}`}
        subtitle="One-time code the officer sends to the bot."

        footer={(
          <>
            <Button variant="secondary" onClick={() => { setInviteFor(null); setInvitation(null); }}>
              Close
            </Button>
            <Button loading={busy === 'invite'} onClick={createInvitation}>
              {invitation ? 'Generate a new code' : 'Generate invitation code'}
            </Button>
          </>
        )}>
        <div className="space-y-3">
          <Field label="Code validity">
            <Select value={inviteTtl} onChange={(e) => setInviteTtl(e.target.value)}>
              <option value={24}>24 hours</option>
              <option value={48}>48 hours</option>
              <option value={168}>7 days</option>
            </Select>
          </Field>

          {invitation && (
            <div className="rounded-lg border border-blue-200 bg-blue-50 p-4 text-center">
              <p className="text-[11px] text-slate-600">Invitation code</p>
              <p className="mt-1 font-mono text-[18px] font-semibold text-slate-900">
                {invitation.code}
              </p>

              <p className="mt-1 text-[11px] text-blue-700">
                Expires {new Date(invitation.expires_at).toLocaleString('en-IN')}
              </p>
              <Button size="sm" variant="secondary" className="mt-2"
                onClick={() => copyCode(invitation.code)}>
                <Copy size={12} /> Copy code
              </Button>
            </div>
          )}

          <div className="rounded-lg border border-slate-200 p-3">
            <p className="text-xs font-semibold text-slate-700">Officer steps</p>
            <ol className="mt-1 list-decimal space-y-0.5 pl-4 text-[11px] text-slate-600">
              <li>Open the grievance bot in Telegram and press Start.</li>
              <li>Send <code className="rounded-sm bg-slate-100 px-1">/officer {invitation?.code || 'GRV-XXXXXXXX'}</code>
                {' '}or paste the code.</li>
              <li>The account links immediately. Assignments arrive with action buttons.</li>
            </ol>
            <p className="mt-2 text-[11px] text-slate-500">
              Single use. One Telegram account per officer.
            </p>

          </div>

          {!invitation && (
            <InlineAlert tone="info">
              Generating a code revokes any unused codes for this officer.
            </InlineAlert>
          )}

        </div>
      </Modal>

      <ConfirmDialog open={Boolean(confirm)} title={confirm?.title} message={confirm?.message}
        confirmLabel={confirm?.label} tone={confirm?.tone} loading={Boolean(busy)}
        onCancel={() => setConfirm(null)} onConfirm={() => confirm?.action()} />
    </div>
  );
}





