import React from 'react';
import { PieChart, Pie, Cell, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { ShieldCheck } from 'lucide-react';
import type { DemoDistributionSlice } from '@/types/overview';
import { TONE_CLASSES } from '@/utils/tones';
import SectionCard from '@/components/SectionCard';

interface ComplianceDistributionChartProps {
  data: DemoDistributionSlice[];
}

export const ComplianceDistributionChart: React.FC<ComplianceDistributionChartProps> = ({ data }) => {
  const hasData = data && data.some((slice) => slice.value > 0);

  return (
    <SectionCard title="PPE Compliance Distribution" subtitle="Active session compliance ratio">
      <div className="h-64" role="img" aria-label="Donut chart of PPE compliance distribution">
        {hasData ? (
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={data}
                dataKey="value"
                nameKey="name"
                innerRadius="55%"
                outerRadius="80%"
                paddingAngle={2}
                stroke="none"
              >
                {data.map((slice) => (
                  <Cell key={slice.name} fill={TONE_CLASSES[slice.tone].hex} />
                ))}
              </Pie>
              <Tooltip formatter={(value) => [`${value} workers`, 'Status']} />
              <Legend
                verticalAlign="bottom"
                iconType="circle"
                formatter={(value) => <span className="text-xs text-slate-600">{value}</span>}
              />
            </PieChart>
          </ResponsiveContainer>
        ) : (
          <div className="flex h-full flex-col items-center justify-center text-center text-slate-500">
            <ShieldCheck className="h-8 w-8 text-slate-400" />
            <p className="mt-2 text-xs font-semibold text-slate-700">No active workers evaluated</p>
            <p className="text-[11px] text-slate-400">
              Start camera monitoring to evaluate live worker compliance.
            </p>
          </div>
        )}
      </div>
    </SectionCard>
  );
};

export default ComplianceDistributionChart;
