import React from 'react';
import {
  HardHat,
  Shield,
  Hand,
  Glasses,
  ShieldCheck,
  Footprints,
  CheckCircle2,
  AlertTriangle,
  HelpCircle,
} from 'lucide-react';
import type { PPECategoryComplianceSummary, PPEStandardCategory } from '@/types/compliance';

interface CategoryComplianceCardProps {
  data: PPECategoryComplianceSummary;
}

const CATEGORY_ICONS: Record<PPEStandardCategory, React.ComponentType<{ className?: string }>> = {
  Hardhat: HardHat,
  'Safety Vest': Shield,
  Gloves: Hand,
  Goggles: Glasses,
  Mask: ShieldCheck,
  'Safety Shoes': Footprints,
};

export const CategoryComplianceCard: React.FC<CategoryComplianceCardProps> = ({ data }) => {
  const Icon = CATEGORY_ICONS[data.category] || Shield;

  const rateTone =
    data.complianceRate >= 95
      ? 'text-emerald-700 bg-emerald-50 border-emerald-200'
      : data.complianceRate >= 80
      ? 'text-blue-700 bg-blue-50 border-blue-200'
      : 'text-amber-700 bg-amber-50 border-amber-200';

  const barColor =
    data.complianceRate >= 95
      ? 'bg-emerald-500'
      : data.complianceRate >= 80
      ? 'bg-blue-600'
      : 'bg-amber-500';

  return (
    <div className="glass-card flex flex-col justify-between rounded-2xl p-5 transition-shadow hover:shadow-md">
      <div>
        <div className="flex items-start justify-between gap-2">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-slate-100 text-slate-700 ring-1 ring-slate-200">
              <Icon className="h-5 w-5" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-slate-900">{data.category}</h3>
              <p className="text-xs text-slate-500">{data.totalMonitored} workers monitored</p>
            </div>
          </div>
        </div>

        {/* Progress & Rate */}
        <div className="mt-4">
          <div className="flex items-baseline justify-between">
            <span className="text-2xl font-bold tracking-tight text-slate-900">
              {data.complianceRate.toFixed(1)}%
            </span>
            <span className={`inline-flex rounded-full border px-2 py-0.5 text-[11px] font-semibold ${rateTone}`}>
              Compliance Rate
            </span>
          </div>

          {/* Progress bar indicator */}
          <div className="mt-2.5 h-2 w-full overflow-hidden rounded-full bg-slate-100">
            <div
              className={`h-full rounded-full transition-all duration-500 ${barColor}`}
              style={{ width: `${Math.min(100, Math.max(0, data.complianceRate))}%` }}
              role="progressbar"
              aria-valuenow={data.complianceRate}
              aria-valuemin={0}
              aria-valuemax={100}
            />
          </div>
        </div>
      </div>

      {/* Metrics Row */}
      <div className="mt-5 grid grid-cols-3 gap-2 border-t border-slate-100 pt-3 text-center">
        <div className="rounded-lg bg-emerald-50/50 p-1.5">
          <div className="flex items-center justify-center gap-1 text-[11px] font-medium text-emerald-800">
            <CheckCircle2 className="h-3 w-3 text-emerald-600" />
            Compliant
          </div>
          <p className="mt-0.5 text-sm font-bold text-emerald-700">{data.compliantCount}</p>
        </div>

        <div className="rounded-lg bg-rose-50/50 p-1.5">
          <div className="flex items-center justify-center gap-1 text-[11px] font-medium text-rose-800">
            <AlertTriangle className="h-3 w-3 text-rose-600" />
            Violations
          </div>
          <p className="mt-0.5 text-sm font-bold text-rose-700">{data.violationCount}</p>
        </div>

        <div className="rounded-lg bg-amber-50/50 p-1.5">
          <div className="flex items-center justify-center gap-1 text-[11px] font-medium text-amber-800">
            <HelpCircle className="h-3 w-3 text-amber-600" />
            Review
          </div>
          <p className="mt-0.5 text-sm font-bold text-amber-700">{data.reviewCount}</p>
        </div>
      </div>
    </div>
  );
};

export default CategoryComplianceCard;

