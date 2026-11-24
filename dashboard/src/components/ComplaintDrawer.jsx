// Slide-over complaint detail: evidence, location, AI verdict, history, actions.
import React, { useEffect, useMemo, useState } from 'react';
import {
  ArrowUpCircle, CheckCircle2, Clock, ExternalLink, ImageOff, MapPin, PauseCircle,
  PlayCircle, RotateCcw, Send, X,
} from 'lucide-react';
import AuthImage from '../AuthImage';
import { ComplaintApi, OfficerApi, apiErrorMessage } from '../services/apiV2';
import { canManage, fmtDateTime, minutesLabel, titleCase } from '../lib/utils';
import { imageFor, imageSrc } from '../lib/media';
import { useFetch } from '../hooks/useFetch';
import { Button, Select, Textarea } from './controls';
import { ConfirmDialog } from './overlays';
import { LevelBadge, SeverityBadge, StatusBadge, VerificationBadge } from './ui';
import { ErrorState, InlineAlert, LoadingBlock } from './feedback';
import { useToast } from './Toast';

function Evidence({ label, image }) {
  const src = imageSrc(image);
  return (
    <div>
      <p className="text-[11px] text-slate-500 mb-1">{label}</p>

      <div className="aspect-[4/3] overflow-hidden rounded-lg border border-slate-200 bg-slate-50">
        {src ? (
          <AuthImage src={src} alt={label} className="h-full w-full object-cover" />
        ) : (
          <div className="h-full w-full grid place-items-center text-slate-300">
            <span className="flex items-center gap-1 text-[11px]"><ImageOff size={14} /> Not uploaded</span>
          </div>
        )}
      </div>
    </div>
  );
}

function Meta({ label, children }) {
  return (
    <div>
      <p className="text-[11px] text-slate-500">{label}</p>
      <div className="text-[12px] text-slate-700">{children ?? '—'}</div>
    </div>
  );
}


export default function ComplaintDrawer({ complaintId, token, onClose, onChanged }) {
  const toast = useToast();
  const [busy, setBusy] = useState('');
  const [assignTo, setAssignTo] = useState('');
  const [resolveNotes, setResolveNotes] = useState('');
  const [confirm, setConfirm] = useState(null);
  const manage = canManage(token);

  const detail = useFetch(() => ComplaintApi.get(complaintId), [complaintId],
    { enabled: Boolean(complaintId) });
  const officers = useFetch(() => OfficerApi.list({}), [],
    { enabled: Boolean(complaintId) && manage });

  const complaint = detail.data;
  useEffect(() => { setAssignTo(''); setResolveNotes(''); }, [complaintId]);

  const departmentOfficers = useMemo(
    () => (officers.data || []).filter((officer) => officer.active &&
      (!complaint?.department_id || officer.department_id === complaint.department_id)),
    [officers.data, complaint]
  );

  const run = async (label, action, successMessage) => {
    setBusy(label);
    try {
      await action();
      toast.push(successMessage, 'success');
      detail.reload();
      onChanged?.();
    } catch (err) {
      toast.push(apiErrorMessage(err), 'error');
    } finally {
      setBusy('');
      setConfirm(null);
    }
  };

  if (!complaintId) return null;

  return (
    <div className="fixed inset-0 z-50 flex">
      <div className="absolute inset-0 bg-slate-900/40" onClick={onClose} />
      <aside className="relative ml-auto h-full w-full max-w-2xl bg-white shadow-2xl flex flex-col">
        <header className="flex items-start justify-between gap-3 px-5 py-4 border-b border-slate-200">
          <div>
            <p className="text-[11px] text-slate-500">Complaint</p>
            <h2 className="font-mono text-[15px] font-semibold text-slate-900">
              {complaint?.ticket_ref || complaintId}
            </h2>

            {complaint && (
              <div className="flex flex-wrap items-center gap-1.5 mt-1">
                <StatusBadge status={complaint.status} />
                <SeverityBadge severity={complaint.severity} />
                <LevelBadge level={complaint.level} />
                <VerificationBadge verdict={complaint.resolution_verification} />
              </div>
            )}
          </div>
          <button onClick={onClose} className="p-1.5 rounded-md text-slate-400 hover:bg-slate-100">
            <X size={18} />
          </button>
        </header>

        <div className="flex-1 overflow-y-auto px-5 py-4 space-y-5">
          {detail.loading && <LoadingBlock />}
          {detail.error && <ErrorState message={detail.error} onRetry={detail.reload} />}

          {complaint && (
            <>
              <div className="grid grid-cols-2 gap-3">
                <Evidence label="Original photo" image={imageFor(complaint.images, 'original')} />
                <Evidence label="Resolution photo" image={imageFor(complaint.images, 'resolution')} />
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 rounded-lg bg-slate-50 border border-slate-200 p-3">
                <Meta label="Department">{complaint.department || 'Unassigned'}</Meta>
                <Meta label="Category">{complaint.category || 'Unclassified'}</Meta>
                <Meta label="Officer">{complaint.assigned_officer || 'Not assigned'}</Meta>
                <Meta label="TAT">
                  {['RESOLVED', 'CLOSED', 'VERIFIED'].includes(complaint.status)
                    ? 'Closed' : minutesLabel(complaint.minutes_remaining)}
                </Meta>
                <Meta label="Ward / Block">{complaint.ward || complaint.block || complaint.area || '—'}</Meta>
                <Meta label="Pincode">{complaint.pincode || '—'}</Meta>
                <Meta label="Created">{fmtDateTime(complaint.created_at)}</Meta>
                <Meta label="Acknowledged">{fmtDateTime(complaint.acknowledged_at)}</Meta>
                <Meta label="Escalations">{complaint.escalation_count}</Meta>
                <Meta label="Reopened">{complaint.reopened_count}</Meta>
                <Meta label="AI confidence">
                  {complaint.ai_confidence ? `${Math.round(complaint.ai_confidence * 100)}%` : '—'}
                </Meta>
                <Meta label="Duplicate group">{complaint.group_id ? 'Linked report' : 'Single report'}</Meta>
              </div>

              <div>
                <p className="text-[11px] text-slate-500 mb-1">
                  Citizen description
                </p>
                <p className="text-[12px] leading-5 text-slate-700">{complaint.description || '—'}</p>

              </div>

              <div className="flex flex-wrap items-center gap-3 text-xs">
                <span className="inline-flex items-center gap-1 text-slate-600">
                  <MapPin size={13} />
                  {complaint.lat != null ? complaint.lat.toFixed(5) : '—'},
                  {' '}{complaint.lon != null ? complaint.lon.toFixed(5) : '—'}
                </span>
                {complaint.map_link && (
                  <a href={complaint.map_link} target="_blank" rel="noreferrer"
                    className="inline-flex items-center gap-1 font-semibold text-blue-700 hover:underline">
                    Open map <ExternalLink size={12} />
                  </a>
                )}
                {complaint.sla_paused && (
                  <span className="inline-flex items-center gap-1 rounded bg-amber-50 border border-amber-200 px-2 py-0.5 text-amber-700">
                    <PauseCircle size={12} /> SLA paused
                  </span>
                )}
              </div>

              {complaint.feedback?.length > 0 && (
                <section>
                  <h4 className="text-[11px] font-medium text-slate-500 mb-2">
                    Citizen feedback
                  </h4>

                  <ul className="space-y-1.5">
                    {complaint.feedback.map((entry, index) => (
                      <li key={index} className="rounded-lg border border-slate-200 px-3 py-2 text-xs">
                        <span className="font-semibold text-slate-700">
                          {entry.rating ? `★ ${entry.rating}/5` : 'No rating'}
                        </span>
                        <span className="text-slate-500">
                          {' '}· {entry.confirmed ? 'Confirmed resolved' : 'Reported still open'}
                        </span>
                        {entry.comment && <p className="text-slate-600 mt-0.5">{entry.comment}</p>}
                      </li>
                    ))}
                  </ul>
                </section>
              )}

              <section>
                <h4 className="text-[11px] font-medium text-slate-500 mb-2 flex items-center gap-1">
                  <Clock size={12} /> Complaint history
                </h4>

                <ol className="border-l border-slate-200 ml-1.5 space-y-3">
                  {(complaint.history || []).map((entry, index) => (
                    <li key={index} className="pl-3 relative">
                      <span className="absolute -left-[5px] top-1.5 h-2 w-2 rounded-full bg-blue-600" />
                      <p className="text-xs font-semibold text-slate-800">{titleCase(entry.action)}</p>
                      <p className="text-[11px] text-slate-500">
                        {entry.actor_type}{entry.actor_id ? ` · ${entry.actor_id}` : ''} · {fmtDateTime(entry.at)}
                      </p>
                      {entry.note && <p className="text-[11px] text-slate-600">{entry.note}</p>}
                    </li>
                  ))}
                </ol>
              </section>

              {complaint.escalations?.length > 0 && (
                <section>
                  <h4 className="text-[11px] font-medium text-slate-500 mb-2">
                    Escalation history
                  </h4>

                  <ul className="space-y-1.5">
                    {complaint.escalations.map((entry, index) => (
                      <li key={index} className="rounded-lg border border-orange-200 bg-orange-50/60 px-3 py-2 text-xs">
                        <p className="font-semibold text-orange-900">
                          L{entry.from_level} → L{entry.to_level} {entry.automatic ? '(automatic)' : '(manual)'}
                        </p>
                        <p className="text-orange-800">{entry.reason}</p>
                        <p className="text-[11px] text-orange-700/80">{fmtDateTime(entry.at)}</p>
                      </li>
                    ))}
                  </ul>
                </section>
              )}
            </>
          )}
        </div>

        {complaint && manage && (
          <footer className="border-t border-slate-200 bg-slate-50 px-5 py-3 space-y-2">
            {complaint.status === 'NEEDS_REVIEW' && (
              <InlineAlert tone="warning">
                This complaint is waiting for administrative review. Assign an officer to start the TAT.
              </InlineAlert>
            )}
            <div className="flex flex-wrap items-center gap-2">
              <Select value={assignTo} onChange={(e) => setAssignTo(e.target.value)}
                className="w-auto min-w-[190px] !py-1.5 text-xs">
                <option value="">Assign officer…</option>
                {departmentOfficers.map((officer) => (
                  <option key={officer.id} value={officer.id}>
                    {officer.full_name} (L{officer.level})
                  </option>
                ))}
              </Select>
              <Button size="sm" variant="secondary" loading={busy === 'assign'} disabled={!assignTo}
                onClick={() => run('assign', () => ComplaintApi.assign(complaint.id,
                  { officer_id: assignTo, reason: 'assigned from dashboard' }), 'Officer assigned')}>
                <Send size={13} /> Assign
              </Button>
              <Button size="sm" variant="secondary" loading={busy === 'ack'}
                onClick={() => run('ack', () => ComplaintApi.acknowledge(complaint.id),
                  'Complaint acknowledged')}>
                <CheckCircle2 size={13} /> Acknowledge
              </Button>
              <Button size="sm" variant="secondary" loading={busy === 'progress'}
                onClick={() => run('progress', () => ComplaintApi.progress(complaint.id,
                  'work started from dashboard'), 'Marked in progress')}>
                In progress
              </Button>
              <Button size="sm" variant="secondary" loading={busy === 'escalate'}
                disabled={complaint.level >= 4}
                onClick={() => setConfirm({
                  title: 'Escalate complaint?',
                  message: `${complaint.ticket_ref} will move from L${complaint.level} to L${complaint.level + 1} and notify the next officer.`,
                  label: 'Escalate', tone: 'primary',
                  action: () => run('escalate', () => ComplaintApi.escalate(complaint.id,
                    'manual escalation'), 'Complaint escalated'),
                })}>
                <ArrowUpCircle size={13} /> Escalate
              </Button>
              {complaint.sla_paused ? (
                <Button size="sm" variant="secondary" loading={busy === 'resume'}
                  onClick={() => run('resume', () => ComplaintApi.resume(complaint.id), 'SLA resumed')}>
                  <PlayCircle size={13} /> Resume SLA
                </Button>
              ) : (
                <Button size="sm" variant="secondary"
                  onClick={() => setConfirm({
                    title: 'Pause the TAT clock?',
                    message: 'Only use this while waiting on the citizen or a third party. The reason is stored in the audit trail.',
                    label: 'Pause', tone: 'primary',
                    action: () => {
                      const reason = window.prompt('Reason for pausing the SLA?') || '';
                      if (reason.trim().length < 3) { toast.push('A reason is required', 'error'); return; }
                      run('pause', () => ComplaintApi.pause(complaint.id, reason), 'SLA paused');
                    },
                  })}>
                  <PauseCircle size={13} /> Pause SLA
                </Button>
              )}
              <Button size="sm" variant="secondary" loading={busy === 'reopen'}
                onClick={() => setConfirm({
                  title: 'Reopen complaint?',
                  message: 'The complaint returns to L1 and the TAT restarts. Full history is preserved.',
                  label: 'Reopen', tone: 'danger',
                  action: () => run('reopen', () => ComplaintApi.reopen(complaint.id,
                    'reopened by administrator'), 'Complaint reopened'),
                })}>
                <RotateCcw size={13} /> Reopen
              </Button>
            </div>
            <div className="flex flex-col sm:flex-row gap-2">
              <Textarea rows={2} value={resolveNotes} onChange={(e) => setResolveNotes(e.target.value)}
                placeholder="Resolution notes (optional)…" className="text-xs" />
              <Button size="sm" variant="success" loading={busy === 'resolve'}
                onClick={() => run('resolve', () => ComplaintApi.resolve(complaint.id,
                  { notes: resolveNotes, run_verification: true }), 'Complaint marked resolved')}>
                Mark resolved
              </Button>
            </div>
          </footer>
        )}
      </aside>

      <ConfirmDialog open={Boolean(confirm)} title={confirm?.title} message={confirm?.message}
        confirmLabel={confirm?.label} tone={confirm?.tone} loading={Boolean(busy)}
        onCancel={() => setConfirm(null)} onConfirm={() => confirm?.action()} />
    </div>
  );
}


