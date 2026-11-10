import React from 'react';
import type { Tone } from '@/types/overview';
import type { ComplianceLabel } from '@/types/liveMonitoring';
import { TONE_CLASSES } from '@/utils/tones';

export const COMPLIANCE_TONE: Record<ComplianceLabel, Tone> = {
  Compliant: 'green',
  Violation: 'red',
  'Needs Review': 'amber',
  'Not Detected': 'slate',
};

interface StatusPillProps {
  tone: Tone;
  children: React.ReactNode;
}

/** Small rounded status badge using the shared tone palette. */
export const StatusPill: React.FC<StatusPillProps> = ({ tone, children }) => (
  <span
    className={`inline-flex whitespace-nowrap rounded-full border px-2.5 py-0.5 text-xs font-semibold ${TONE_CLASSES[tone].badge}`}
  >
    {children}
  </span>
);

export const ComplianceBadge: React.FC<{ status: ComplianceLabel }> = ({ status }) => (
  <StatusPill tone={COMPLIANCE_TONE[status]}>{status}</StatusPill>
);

export default StatusPill;

