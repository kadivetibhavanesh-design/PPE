import React from 'react';
import { Construction } from 'lucide-react';
import { getNavItem } from '@/utils/navigation';

interface PlaceholderPageProps {
  /** Route path of the page, used to look up its title, icon and description. */
  path: string;
}

export const PlaceholderPage: React.FC<PlaceholderPageProps> = ({ path }) => {
  const item = getNavItem(path);
  if (!item) return null;
  const Icon = item.icon;

  return (
    <section className="glass-card max-w-3xl rounded-2xl p-6 sm:p-8">
      <div className="flex flex-col gap-5 sm:flex-row sm:items-start">
        <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-blue-50 text-blue-700 ring-1 ring-blue-100">
          <Icon className="h-6 w-6" />
        </div>
        <div className="space-y-3">
          <h2 className="text-2xl font-bold tracking-tight text-slate-900">{item.label}</h2>
          <p className="text-sm leading-relaxed text-slate-600 sm:text-base">{item.description}</p>
          <div className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs font-semibold text-slate-600">
            <Construction className="h-3.5 w-3.5" />
            Implementation pending
          </div>
        </div>
      </div>
    </section>
  );
};

export default PlaceholderPage;

