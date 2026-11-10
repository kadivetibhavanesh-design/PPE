import React from 'react';
import { CircleDot } from 'lucide-react';

interface PageHeaderProps {
  title: string;
  description: string;
  /** Text of the monitoring status badge. */
  statusLabel?: string;
  /** Optional custom badge. */
  badge?: React.ReactNode;
  /** Optional custom header actions. */
  actions?: React.ReactNode;
}

/** Page title block with system status badge and actions. */
export const PageHeader: React.FC<PageHeaderProps> = ({
  title,
  description,
  statusLabel,
  badge,
  actions,
}) => {
  const isPositiveStatus = statusLabel && (
    statusLabel.toLowerCase().includes('active') ||
    statusLabel.toLowerCase().includes('online') ||
    statusLabel.toLowerCase().includes('ready')
  );

  return (
    <header className="glass-card rounded-2xl p-5 sm:p-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="space-y-1.5">
          <div className="flex flex-wrap items-center gap-3">
            <h2 className="text-2xl font-bold tracking-tight text-slate-900">{title}</h2>
            {badge}
          </div>
          <p className="max-w-2xl text-sm text-slate-600">{description}</p>
        </div>

        <div className="flex flex-wrap items-center gap-2.5">
          {actions}
          {statusLabel && (
            <span
              className={`inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-semibold ${
                isPositiveStatus
                  ? 'border-emerald-200 bg-emerald-50 text-emerald-800'
                  : 'border-slate-300 bg-slate-100 text-slate-700'
              }`}
            >
              {isPositiveStatus ? (
                <>
                  <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
                  {statusLabel}
                </>
              ) : (
                <>
                  <CircleDot className="h-3 w-3 text-slate-400" />
                  {statusLabel}
                </>
              )}
            </span>
          )}
        </div>
      </div>
    </header>
  );
};

export default PageHeader;

