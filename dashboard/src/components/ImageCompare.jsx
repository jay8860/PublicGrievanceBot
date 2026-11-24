// Before / after evidence comparison with verification banner.
import React from 'react';
import { ImageOff } from 'lucide-react';
import AuthImage from '../AuthImage';
import { VerificationBadge } from './ui';
import { cls } from '../lib/utils';
import { imageSrc } from '../lib/media';

function Panel({ label, tone, image }) {
  const src = imageSrc(image);
  return (
    <figure className="flex-1 min-w-[240px]">
      <figcaption className={cls('mb-1 text-[11px]', tone)}>
        {label}
      </figcaption>
      <div className="aspect-[4/3] overflow-hidden rounded-lg border border-slate-200 bg-slate-50">
        {src ? (
          <AuthImage src={src} alt={label} className="h-full w-full object-cover" />
        ) : (
          <div className="h-full w-full grid place-items-center text-slate-300">
            <span className="flex items-center gap-1 text-[11px]"><ImageOff size={14} /> Not available</span>
          </div>
        )}
      </div>
    </figure>
  );
}

export default function ImageCompare({ original, resolution, verdict }) {
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <span className="text-[11px] text-slate-500">Before and after</span>
        <VerificationBadge verdict={verdict} />
      </div>
      <div className="flex flex-wrap gap-3">
        <Panel label="Before (citizen)" tone="text-slate-600" image={original} />
        <Panel label="After (officer)" tone="text-emerald-700" image={resolution} />
      </div>

    </div>
  );
}
