import React, { useMemo, useState } from 'react';
import { CheckCircle2, RotateCcw, ShieldQuestion, XCircle } from 'lucide-react';
import ImageCompare from '../components/ImageCompare';
import { Button, Textarea } from '../components/controls';
import { Modal, Tabs } from '../components/overlays';
import { Card, CardHeader, LevelBadge, SeverityBadge, StatusBadge, VerificationBadge } from '../components/ui';
import { EmptyState, ErrorState, LoadingBlock } from '../components/feedback';
import { useToast } from '../components/Toast';
import { useFetch } from '../hooks/useFetch';
import { canManage, fmtDateTime } from '../lib/utils';
import { imageFor } from '../lib/media';
import { ComplaintApi, VerificationApi, apiErrorMessage } from '../services/apiV2';

const FILTERS = [
  { value: '', label: 'All' },
  { value: 'requires_review', label: 'Needs review' },
  { value: 'verified', label: 'Verified' },
  { value: 'failed', label: 'Failed' },
];

export default function ResolutionVerification({ token }) {
  const toast = useToast();
  const [verdict, setVerdict] = useState('');
  const [action, setAction] = useState(null);
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState(false);
  const manage = canManage(token);

  const queue = useFetch(() => VerificationApi.list(verdict || undefined), [verdict]);
  const rows = queue.data || [];

  const counts = useMemo(() => rows.reduce((acc, row) => {
    const key = row.resolution_verification || 'pending';
    acc[key] = (acc[key] || 0) + 1;
    return acc;
  }, {}), [rows]);

  const apply = async () => {
    if (!action) return;
    setBusy(true);
    try {
      await ComplaintApi.verify(action.complaint.id, { action: action.type, note });
      toast.push(`Resolution ${action.type.replace('_', ' ')} recorded`, 'success');
      setAction(null);
      setNote('');
      queue.reload();
    } catch (err) {
      toast.push(apiErrorMessage(err), 'error');
    } finally {
      setBusy(false);
    }
  };

  if (queue.loading && !queue.data) return <LoadingBlock label="Loading verification queue…" />;
  if (queue.error) return <ErrorState message={queue.error} onRetry={queue.reload} />;

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader title="Resolution evidence"
          subtitle="The AI verdict is a suggestion; your decision is logged" />

        <div className="px-4 pt-3">
          <Tabs value={verdict} onChange={setVerdict}
            tabs={FILTERS.map((filter) => ({
              value: filter.value, label: filter.label,
              count: filter.value ? counts[filter.value] ?? 0 : rows.length,
            }))} />
        </div>
        <p className="px-4 py-3 text-[11px] text-slate-500">
          A resolution the photo check confirms is approved automatically. What lands here is what
          the check could not decide (no key, unclear photos, different location) plus disputed
          closures. Approve marks it verified; reject reopens it at L1 with history kept.
        </p>


      </Card>

      {rows.length === 0 ? (
        <Card>
          <EmptyState title="Nothing to verify"
            message="Cases appear after an officer submits an after photo." />

        </Card>
      ) : (
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
          {rows.map((complaint) => (
            <Card key={complaint.id}>
              <CardHeader
                title={complaint.ticket_ref}
                subtitle={`${complaint.department || 'Unassigned'} · resolved ${fmtDateTime(complaint.resolved_at)}`}
                actions={<VerificationBadge verdict={complaint.resolution_verification} />} />
              <div className="p-4 space-y-3">
                <div className="flex flex-wrap items-center gap-1.5">
                  <StatusBadge status={complaint.status} />
                  <SeverityBadge severity={complaint.severity} />
                  <LevelBadge level={complaint.level} />
                  <span className="text-[11px] text-slate-500">
                    {complaint.assigned_officer || 'No officer'}
                  </span>
                </div>
                <p className="text-xs text-slate-600">{complaint.description}</p>

                {complaint.status === 'VERIFIED' && complaint.resolution_verification === 'verified' && (
                  <p className="text-[11px] text-emerald-700">
                    Approved by the photo check. Override below if the evidence says otherwise.
                  </p>
                )}

                <ImageCompare
                  original={imageFor(complaint.images, 'original')}
                  resolution={imageFor(complaint.images, 'resolution')}
                  verdict={complaint.resolution_verification} />

                <div className="rounded-lg border border-slate-200 px-3 py-2 text-[11px] text-slate-600">
                  <p className="font-semibold text-slate-700">Citizen feedback</p>
                  {complaint.feedback?.length
                    ? complaint.feedback.map((entry, index) => (
                        <p key={index}>
                          {entry.rating ? `★ ${entry.rating}/5` : 'No rating'} ·{' '}
                          {entry.confirmed ? 'confirmed resolved' : 'reported still open'}
                          {entry.comment ? ` · ${entry.comment}` : ''}
                        </p>
                      ))
                    : <p className="text-slate-400">No feedback yet</p>}
                </div>

                {manage && (
                  <div className="flex flex-wrap gap-2">
                    <Button size="sm" variant="success"
                      onClick={() => { setAction({ complaint, type: 'approve' }); setNote(''); }}>
                      <CheckCircle2 size={13} /> Approve
                    </Button>
                    <Button size="sm" variant="danger"
                      onClick={() => { setAction({ complaint, type: 'reject' }); setNote(''); }}>
                      <XCircle size={13} /> Reject
                    </Button>
                    <Button size="sm" variant="secondary"
                      onClick={() => { setAction({ complaint, type: 'request_review' }); setNote(''); }}>
                      <ShieldQuestion size={13} /> Manual review
                    </Button>
                    <Button size="sm" variant="ghost"
                      onClick={() => { setAction({ complaint, type: 'reopen' }); setNote(''); }}>
                      <RotateCcw size={13} /> Reopen
                    </Button>
                  </div>
                )}
              </div>
            </Card>
          ))}
        </div>
      )}

      <Modal open={Boolean(action)} onClose={() => setAction(null)}
        title={`${(action?.type || '').replace('_', ' ')} · ${action?.complaint?.ticket_ref || ''}`}
        subtitle="The decision and note are written to the audit log."
        footer={(
          <>
            <Button variant="secondary" onClick={() => setAction(null)}>Cancel</Button>
            <Button loading={busy} onClick={apply}>Record decision</Button>
          </>
        )}>
        <div className="space-y-3">
          <Textarea rows={3} value={note} onChange={(e) => setNote(e.target.value)}
            placeholder="Reason / note for the record (optional but recommended)…" />
          <div className="rounded-md bg-slate-50 border border-slate-200 px-3 py-2 text-[11px] text-slate-600">
            AI verdict: <b>{action?.complaint?.resolution_verification || 'not available'}</b>.
            Decide from the before and after photos.
          </div>

        </div>
      </Modal>
    </div>
  );
}

