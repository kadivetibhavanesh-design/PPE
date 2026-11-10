import React from 'react';

interface SectionCardProps {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
  className?: string;
}

/** Rounded glass card with a titled header, reused by all dashboard sections. */
export const SectionCard: React.FC<SectionCardProps> = ({ title, subtitle, children, className = '' }) => (
  <section className={`glass-card rounded-2xl p-5 sm:p-6 ${className}`}>
    <div className="mb-4 flex items-start justify-between gap-3">
      <div className="min-w-0">
        <h3 className="text-base font-semibold text-slate-900">{title}</h3>
        {subtitle && <p className="mt-0.5 text-xs text-slate-500">{subtitle}</p>}
      </div>
    </div>
    {children}
  </section>
);

export default SectionCard;

