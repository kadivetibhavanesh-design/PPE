import React from 'react';
import SectionCard from '@/components/SectionCard';
import StatusPill from '@/components/StatusPill';
import type { ViolationEventItem } from '@/types/monitoring';
import { ShieldAlert, CheckCircle2 } from 'lucide-react';
import { formatSeconds } from '@/utils';

interface DetectionEventsTableProps {
  events: ViolationEventItem[];
  isRunning: boolean;
}

export const DetectionEventsTable: React.FC<DetectionEventsTableProps> = React.memo(({
  events,
  isRunning,
}) => {
  return (
    <SectionCard
      title="Live Violation Events"
      subtitle={
        isRunning
          ? `${events.length} active event${events.length === 1 ? '' : 's'} recorded in session`
          : 'Monitoring inactive'
      }
    >
      <div className="-mx-2 overflow-x-auto px-2">
        {events.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-8 text-center text-slate-500">
            {isRunning ? (
              <>
                <CheckCircle2 className="h-8 w-8 text-emerald-500" />
                <p className="mt-2 text-xs font-semibold text-emerald-800">
                  Zero active violation events
                </p>
                <p className="text-[11px] text-slate-400">
                  All active workers satisfy mandatory safety thresholds ({'<'} 5.0s violation limit).
                </p>
              </>
            ) : (
              <>
                <ShieldAlert className="h-8 w-8 text-slate-400" />
                <p className="mt-2 text-xs font-semibold text-slate-700">
                  No active monitoring session
                </p>
                <p className="text-[11px] text-slate-400">
                  When a continuous violation exceeds the 5-second threshold, events are logged here in real-time.
                </p>
              </>
            )}
          </div>
        ) : (
          <table className="w-full min-w-[560px] text-left text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-xs uppercase tracking-wide text-slate-500">
                <th className="py-2.5 pr-3 font-semibold">Event ID</th>
                <th className="py-2.5 pr-3 font-semibold">Worker ID</th>
                <th className="py-2.5 pr-3 font-semibold">Hazard Category</th>
                <th className="py-2.5 pr-3 font-semibold">Severity</th>
                <th className="py-2.5 pr-3 font-semibold">Duration</th>
                <th className="py-2.5 font-semibold">Event Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {events.map((event) => {
                const isCritical = event.severity === 'critical';
                const isHigh = event.severity === 'high';
                const severityTone = isCritical ? 'red' : isHigh ? 'amber' : 'blue';

                const isOngoing = event.status === 'ongoing' || event.status === 'open';
                const statusTone = isOngoing ? 'red' : 'green';

                return (
                  <tr key={event.event_id} className="transition-colors hover:bg-slate-50/60">
                    <td className="py-3 pr-3 font-mono text-xs font-bold text-slate-800">
                      {event.event_id}
                    </td>
                    <td className="py-3 pr-3 font-mono text-xs font-semibold text-brand-700">
                      #{event.worker_track_id.toString().padStart(2, '0')}
                    </td>
                    <td className="py-3 pr-3 font-medium text-slate-800">
                      {event.ppe_category}
                    </td>
                    <td className="py-3 pr-3">
                      <StatusPill tone={severityTone}>
                        {event.severity.toUpperCase()}
                      </StatusPill>
                    </td>
                    <td className="py-3 pr-3 tabular-nums text-xs font-semibold text-rose-700">
                      {formatSeconds(event.duration_seconds)}
                    </td>
                    <td className="py-3">
                      <StatusPill tone={statusTone}>
                        {event.status.toUpperCase()}
                      </StatusPill>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </SectionCard>
  );
});

export default DetectionEventsTable;
