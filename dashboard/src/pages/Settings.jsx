import React, { useState } from 'react';
import { CheckCircle2, ShieldAlert, UserPlus } from 'lucide-react';
import { Button, Field, Input, Select } from '../components/controls';
import { Card, CardHeader } from '../components/ui';
import { ErrorState, InlineAlert, LoadingBlock } from '../components/feedback';
import { useToast } from '../components/Toast';
import { useFetch } from '../hooks/useFetch';
import { isSuperadmin, ROLES, roleOf } from '../lib/utils';
import { AdminApi, AuthApi, SecurityApi, apiErrorMessage } from '../services/apiV2';

function Flag({ ok, label, detail }) {
  return (
    <div className="flex items-start gap-2 rounded-lg border border-slate-200 px-3 py-2">
      {ok ? <CheckCircle2 size={16} className="mt-0.5 text-emerald-600" />
        : <ShieldAlert size={16} className="mt-0.5 text-red-600" />}
      <div>
        <p className="text-xs font-semibold text-slate-800">{label}</p>
        <p className="text-[11px] text-slate-500">{detail}</p>
      </div>
    </div>
  );
}

export default function Settings({ token }) {
  const toast = useToast();
  const me = useFetch(() => AuthApi.me(), []);
  const superadmin = isSuperadmin(token);

  const security = useFetch(() => SecurityApi.status(), [], { enabled: superadmin });
  const admins = useFetch(() => AdminApi.list(), [], { enabled: superadmin });

  const [passwords, setPasswords] = useState({ current_password: '', new_password: '', repeat: '' });
  const [newAdmin, setNewAdmin] = useState({ username: '', password: '', role: 'admin' });
  const [busy, setBusy] = useState('');

  const changePassword = async () => {
    if (passwords.new_password.length < 8) {
      toast.push('New password must be at least 8 characters', 'error'); return;
    }
    if (passwords.new_password !== passwords.repeat) {
      toast.push('Passwords do not match', 'error'); return;
    }
    setBusy('password');
    try {
      await AuthApi.changePassword({
        current_password: passwords.current_password,
        new_password: passwords.new_password,
      });
      toast.push('Password updated', 'success');
      setPasswords({ current_password: '', new_password: '', repeat: '' });
    } catch (err) {
      toast.push(apiErrorMessage(err), 'error');
    } finally {
      setBusy('');
    }
  };

  const createAdmin = async () => {
    if (newAdmin.username.trim().length < 3 || newAdmin.password.length < 8) {
      toast.push('Username (3+) and password (8+) are required', 'error'); return;
    }
    setBusy('admin');
    try {
      await AdminApi.create(newAdmin);
      toast.push('Administrator account created', 'success');
      setNewAdmin({ username: '', password: '', role: 'admin' });
      admins.reload();
    } catch (err) {
      toast.push(apiErrorMessage(err), 'error');
    } finally {
      setBusy('');
    }
  };

  const deactivate = async (row) => {
    setBusy(row.id);
    try {
      await AdminApi.deactivate(row.id);
      toast.push(`${row.username} deactivated`, 'success');
      admins.reload();
    } catch (err) {
      toast.push(apiErrorMessage(err), 'error');
    } finally {
      setBusy('');
    }
  };

  if (me.loading) return <LoadingBlock label="Loading settings…" />;
  if (me.error) return <ErrorState message={me.error} onRetry={me.reload} />;

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <Card>
          <CardHeader title="My account" subtitle="Signed-in administrator" />
          <div className="p-4 space-y-3">
            <div className="grid grid-cols-2 gap-3 text-xs">
              <div>
                <p className="text-[11px] text-slate-500">Username</p>
                <p className="text-[12px] font-medium text-slate-800">{me.data?.username}</p>
              </div>
              <div>
                <p className="text-[11px] text-slate-500">Role</p>
                <p className="text-[12px] font-medium text-slate-800">
                  {ROLES[roleOf(token)] || roleOf(token)}
                </p>

              </div>
            </div>
            <div className="border-t border-slate-100 pt-3 space-y-2">
              <p className="text-xs font-semibold text-slate-700">Change password</p>
              <Field label="Current password">
                <Input type="password" value={passwords.current_password}
                  onChange={(e) => setPasswords({ ...passwords, current_password: e.target.value })} />
              </Field>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                <Field label="New password" hint="Minimum 8 characters">
                  <Input type="password" value={passwords.new_password}
                    onChange={(e) => setPasswords({ ...passwords, new_password: e.target.value })} />
                </Field>
                <Field label="Repeat new password">
                  <Input type="password" value={passwords.repeat}
                    onChange={(e) => setPasswords({ ...passwords, repeat: e.target.value })} />
                </Field>
              </div>
              <Button size="sm" loading={busy === 'password'} onClick={changePassword}>
                Update password
              </Button>
            </div>
          </div>
        </Card>

        <Card>
          <CardHeader title="System status"
            subtitle={superadmin
              ? 'Live configuration of this deployment'
              : 'Visible to super administrators only'} />
          <div className="p-4 space-y-2">
            {!superadmin && (
              <InlineAlert tone="info">
                Your role is {ROLES[roleOf(token)]}. Security and administrator settings require the
                superadmin role.
              </InlineAlert>
            )}
            {superadmin && security.loading && <LoadingBlock label="Checking configuration…" />}
            {superadmin && security.error && (
              <ErrorState message={security.error} onRetry={security.reload} />
            )}
            {superadmin && security.data && (
              <>
                <Flag ok={security.data.database_url_set} label="Database"
                  detail={security.data.database} />
                <Flag ok={!security.data.secret_key_is_default} label="JWT secret"
                  detail={security.data.secret_key_is_default
                    ? 'Still the built-in default. Set SECRET_KEY.'
                    : 'Set'} />
                <Flag ok={!security.data.admin_password_is_default} label="Admin password"
                  detail={security.data.admin_password_is_default
                    ? 'Still admin123. Change it.'
                    : 'Changed'} />
                <Flag ok={!security.data.bypass_login} label="Login bypass"
                  detail={security.data.bypass_login ? 'On' : 'Off'} />
                <Flag ok={security.data.scheduler_enabled} label="Escalation scheduler"
                  detail={`Every ${security.data.tick_seconds}s`} />
                <Flag ok={security.data.telegram_token_set} label="Telegram bot token"
                  detail={security.data.telegram_token_set ? 'Set' : 'Not set'} />
                <Flag ok={security.data.openrouter_key_set} label="OpenRouter key"
                  detail={security.data.openrouter_key_set
                    ? 'Set' : 'Not set. Triage and verification will fail.'} />

              </>
            )}
          </div>
        </Card>
      </div>

      {superadmin && (
        <Card>
          <CardHeader title="Administrator accounts" subtitle="One login per person" />

          <div className="p-4 space-y-3">
            <div className="divide-y divide-slate-100 rounded-lg border border-slate-200">
              {(admins.data || []).map((row) => (
                <div key={row.id} className="flex items-center justify-between gap-3 px-3 py-2">
                  <div>
                    <p className="text-sm font-medium text-slate-800">{row.username}</p>
                    <p className="text-[11px] text-slate-500">{ROLES[row.role] || row.role}</p>
                  </div>
                  {row.active ? (
                    <Button size="sm" variant="secondary" loading={busy === row.id}
                      onClick={() => deactivate(row)}>Deactivate</Button>
                  ) : (
                    <span className="text-[11px] font-semibold text-red-600">Inactive</span>
                  )}
                </div>
              ))}
              {(admins.data || []).length === 0 && !admins.loading && (
                <p className="px-3 py-4 text-xs text-slate-500">No database admin accounts yet.</p>
              )}
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-4 gap-2 items-end">
              <Field label="Username">
                <Input value={newAdmin.username}
                  onChange={(e) => setNewAdmin({ ...newAdmin, username: e.target.value })} />
              </Field>
              <Field label="Password" hint="Minimum 8 characters">
                <Input type="password" value={newAdmin.password}
                  onChange={(e) => setNewAdmin({ ...newAdmin, password: e.target.value })} />
              </Field>
              <Field label="Role">
                <Select value={newAdmin.role}
                  onChange={(e) => setNewAdmin({ ...newAdmin, role: e.target.value })}>
                  <option value="admin">Administrator</option>
                  <option value="viewer">Viewer</option>
                  <option value="superadmin">Super admin</option>
                </Select>
              </Field>
              <Button loading={busy === 'admin'} onClick={createAdmin}>
                <UserPlus size={13} /> Add account
              </Button>
            </div>
          </div>
        </Card>
      )}
    </div>
  );
}

