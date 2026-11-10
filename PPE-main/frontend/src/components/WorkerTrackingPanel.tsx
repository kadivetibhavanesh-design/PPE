import React from 'react';
import SectionCard from '@/components/SectionCard';
import StatusPill from '@/components/StatusPill';
import type { MonitoringWorkerItem, ViolationTimerItem } from '@/types/monitoring';
import { Users } from 'lucide-react';
import { formatSeconds } from '@/utils';

interface WorkerTrackingPanelProps {
  workers: MonitoringWorkerItem[];
  violationTimers: ViolationTimerItem[];
  isRunning: boolean;
}

export const WorkerTrackingPanel: React.FC<WorkerTrackingPanelProps> = React.memo(({
  workers,
  violationTimers,
  isRunning,
}) => {
  return (
    <SectionCard
      title="Live Worker Tracking"
      subtitle={
        isRunning
          ? `${workers.length} tracked worker${workers.length === 1 ? '' : 's'} in active session`
          : 'Monitoring inactive'
      }
    >
      <div className="-mx-2 overflow-x-auto px-2">
        {workers.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-8 text-center text-slate-500">
            <Users className="h-8 w-8 text-slate-400" />
            <p className="mt-2 text-xs font-semibold text-slate-700">
              {isRunning
                ? 'No workers currently detected in camera view'
                : 'Awaiting monitoring session start'}
            </p>
            <p className="text-[11px] text-slate-400">
              {isRunning
                ? 'ByteTrack assigns persistent track IDs as workers enter the monitored perimeter.'
                : 'Start monitoring above to view real-time worker tracking telemetry.'}
            </p>
          </div>
        ) : (
          <table className="w-full min-w-[500px] text-left text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-xs uppercase tracking-wide text-slate-500">
                <th className="py-2.5 pr-3 font-semibold">Track ID</th>
                <th className="py-2.5 pr-3 font-semibold">Lifecycle</th>
                <th className="py-2.5 pr-3 font-semibold">PPE Compliance</th>
                <th className="py-2.5 pr-3 font-semibold">Categories</th>
                <th className="py-2.5 font-semibold">Continuous Violation</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {workers.map((worker) => {
                const timer = violationTimers.find(
                  (t) => t.track_id === worker.worker_track_id
                );
                const violationSeconds = timer?.elapsed_seconds ?? 0;

                const isCompliant = worker.overall_status === 'compliant';
                const isViolation =
                  worker.overall_status === 'non_compliant' ||
                  worker.overall_status === 'violation';

                const complianceTone = isCompliant
                  ? 'green'
                  : isViolation
                  ? 'red'
                  : 'amber';

                const formattedStatus = isCompliant
                  ? 'Compliant'
                  : isViolation
                  ? 'Non-Compliant'
                  : 'Needs Review';

                return (
                  <tr key={worker.worker_track_id} className="transition-colors hover:bg-slate-50/60">
                    <td className="py-3 pr-3 font-mono font-bold text-slate-900">
                      #{worker.worker_track_id.toString().padStart(2, '0')}
                    </td>
                    <td className="py-3 pr-3">
                      <StatusPill tone="blue">
                        {worker.lifecycle_status || 'active'}
                      </StatusPill>
                    </td>
                    <td className="py-3 pr-3">
                      <StatusPill tone={complianceTone}>
                        {formattedStatus}
                      </StatusPill>
                    </td>
                    <td className="py-3 pr-3 text-xs text-slate-600">
                      <span className="font-semibold text-emerald-700">
                        {worker.compliant_category_count} pass
                      </span>
                      {' / '}
                      <span
                        className={
                          worker.violation_count > 0
                            ? 'font-bold text-rose-700'
                            : 'text-slate-400'
                        }
                      >
                        {worker.violation_count} fail
                      </span>
                    </td>
                    <td className="py-3 tabular-nums text-xs">
                      {violationSeconds > 0 ? (
                        <span className="inline-flex items-center gap-1 font-bold text-rose-700 bg-rose-50 px-2 py-0.5 rounded border border-rose-200">
                          {formatSeconds(violationSeconds)}
                        </span>
                      ) : (
                        <span className="text-slate-400">0s</span>
                      )}
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

export default WorkerTrackingPanel;
