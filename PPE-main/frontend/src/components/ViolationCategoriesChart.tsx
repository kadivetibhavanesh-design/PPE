import React from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { CheckCircle2 } from 'lucide-react';
import type { DemoCategoryCount } from '@/types/overview';
import SectionCard from '@/components/SectionCard';

interface ViolationCategoriesChartProps {
  data: DemoCategoryCount[];
}

export const ViolationCategoriesChart: React.FC<ViolationCategoriesChartProps> = ({ data }) => {
  const hasData = data && data.some((item) => item.count > 0);

  return (
    <SectionCard title="Violation Categories" subtitle="Breakdown of recorded non-compliance events">
      <div className="h-64" role="img" aria-label="Bar chart of violations by PPE category">
        {hasData ? (
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data} layout="vertical" margin={{ top: 4, right: 12, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" horizontal={false} />
              <XAxis
                type="number"
                allowDecimals={false}
                tick={{ fontSize: 11, fill: '#64748b' }}
                tickLine={false}
                axisLine={false}
              />
              <YAxis
                type="category"
                dataKey="category"
                width={92}
                tick={{ fontSize: 11, fill: '#475569' }}
                tickLine={false}
                axisLine={{ stroke: '#e2e8f0' }}
              />
              <Tooltip cursor={{ fill: '#f1f5f9' }} formatter={(value) => [`${value}`, 'Violations']} />
              <Bar dataKey="count" fill="#ef4444" radius={[0, 6, 6, 0]} maxBarSize={26} />
            </BarChart>
          </ResponsiveContainer>
        ) : (
          <div className="flex h-full flex-col items-center justify-center text-center text-slate-500">
            <CheckCircle2 className="h-8 w-8 text-emerald-500" />
            <p className="mt-2 text-xs font-semibold text-slate-700">No violations recorded</p>
            <p className="text-[11px] text-slate-400">
              All monitored workers are compliant with safety standards.
            </p>
          </div>
        )}
      </div>
    </SectionCard>
  );
};

export default ViolationCategoriesChart;
