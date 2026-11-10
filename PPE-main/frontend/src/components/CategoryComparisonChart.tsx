import React from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import SectionCard from '@/components/SectionCard';

interface CategoryComparisonData {
  category: string;
  compliant: number;
  violations: number;
  needsReview: number;
}

interface CategoryComparisonChartProps {
  data: CategoryComparisonData[];
}

export const CategoryComparisonChart: React.FC<CategoryComparisonChartProps> = ({ data }) => {
  const hasData = data && data.some((d) => d.compliant > 0 || d.violations > 0 || d.needsReview > 0);

  return (
    <SectionCard
      title="PPE Category Comparison"
      subtitle="Compliant, violation, and review counts per equipment standard"
    >
      {!hasData ? (
        <div className="flex h-64 flex-col items-center justify-center text-center text-slate-400 sm:h-72">
          <p className="text-sm font-medium">No PPE evaluation data available</p>
          <p className="mt-1 text-xs text-slate-500">
            Start camera monitoring to track gear compliance across categories.
          </p>
        </div>
      ) : (
        <div className="h-64 sm:h-72" role="img" aria-label="Grouped bar chart comparing compliance across 6 PPE categories">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data} margin={{ top: 12, right: 16, left: -10, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
              <XAxis
                dataKey="category"
                tick={{ fontSize: 11, fill: '#475569' }}
                tickLine={false}
                axisLine={{ stroke: '#cbd5e1' }}
              />
              <YAxis
                allowDecimals={false}
                tick={{ fontSize: 11, fill: '#64748b' }}
                tickLine={false}
                axisLine={false}
                width={35}
              />
              <Tooltip
                cursor={{ fill: '#f8fafc' }}
                contentStyle={{
                  backgroundColor: 'rgba(255, 255, 255, 0.95)',
                  borderRadius: '0.75rem',
                  border: '1px solid #e2e8f0',
                  boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)',
                  fontSize: '12px',
                }}
              />
              <Legend
                verticalAlign="top"
                align="right"
                iconType="circle"
                wrapperStyle={{ paddingBottom: '8px' }}
                formatter={(value) => <span className="text-xs font-medium text-slate-600">{value}</span>}
              />
              <Bar name="Compliant" dataKey="compliant" fill="#10b981" radius={[4, 4, 0, 0]} maxBarSize={22} />
              <Bar name="Violations" dataKey="violations" fill="#ef4444" radius={[4, 4, 0, 0]} maxBarSize={22} />
              <Bar name="Needs Review" dataKey="needsReview" fill="#f59e0b" radius={[4, 4, 0, 0]} maxBarSize={22} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </SectionCard>
  );
};

export default CategoryComparisonChart;

