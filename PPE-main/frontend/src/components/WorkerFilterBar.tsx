import React from 'react';
import { Search, X, Filter, RotateCcw } from 'lucide-react';
import type {
  WorkerTrackingStatus,
  WorkerComplianceStatus,
} from '@/types/workers';

interface WorkerFilterBarProps {
  searchQuery: string;
  onSearchChange: (value: string) => void;
  trackingFilter: 'All' | WorkerTrackingStatus;
  onTrackingFilterChange: (value: 'All' | WorkerTrackingStatus) => void;
  complianceFilter: 'All' | WorkerComplianceStatus;
  onComplianceFilterChange: (value: 'All' | WorkerComplianceStatus) => void;
  onClearFilters: () => void;
  totalCount: number;
  filteredCount: number;
}

export const WorkerFilterBar: React.FC<WorkerFilterBarProps> = ({
  searchQuery,
  onSearchChange,
  trackingFilter,
  onTrackingFilterChange,
  complianceFilter,
  onComplianceFilterChange,
  onClearFilters,
  totalCount,
  filteredCount,
}) => {
  const hasActiveFilters =
    searchQuery.trim().length > 0 ||
    trackingFilter !== 'All' ||
    complianceFilter !== 'All';

  return (
    <div className="glass-card rounded-2xl p-4 sm:p-5">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        {/* Search input */}
        <div className="relative flex-1">
          <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3.5 text-slate-400">
            <Search className="h-4 w-4" />
          </div>
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => onSearchChange(e.target.value)}
            placeholder="Search by worker ID (e.g. 7) or name (e.g. Elena)..."
            className="w-full rounded-xl border border-slate-200 bg-white/80 py-2.5 pl-10 pr-10 text-sm text-slate-900 placeholder:text-slate-400 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20"
          />
          {searchQuery && (
            <button
              type="button"
              onClick={() => onSearchChange('')}
              className="absolute inset-y-0 right-0 flex items-center pr-3 text-slate-400 hover:text-slate-600"
              aria-label="Clear search input"
            >
              <X className="h-4 w-4" />
            </button>
          )}
        </div>

        {/* Filter dropdowns and actions */}
        <div className="flex flex-wrap items-center gap-3">
          {/* Tracking Status Filter */}
          <div className="flex items-center gap-1.5">
            <label htmlFor="tracking-filter" className="text-xs font-medium text-slate-500">
              Tracking:
            </label>
            <select
              id="tracking-filter"
              value={trackingFilter}
              onChange={(e) => onTrackingFilterChange(e.target.value as 'All' | WorkerTrackingStatus)}
              className="rounded-xl border border-slate-200 bg-white/80 px-3 py-2 text-xs font-semibold text-slate-700 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20"
            >
              <option value="All">All Tracking</option>
              <option value="Active">Active</option>
              <option value="Missing">Missing</option>
              <option value="Left">Left</option>
            </select>
          </div>

          {/* Compliance Status Filter */}
          <div className="flex items-center gap-1.5">
            <label htmlFor="compliance-filter" className="text-xs font-medium text-slate-500">
              Compliance:
            </label>
            <select
              id="compliance-filter"
              value={complianceFilter}
              onChange={(e) => onComplianceFilterChange(e.target.value as 'All' | WorkerComplianceStatus)}
              className="rounded-xl border border-slate-200 bg-white/80 px-3 py-2 text-xs font-semibold text-slate-700 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20"
            >
              <option value="All">All Compliance</option>
              <option value="Compliant">Compliant</option>
              <option value="Non-Compliant">Non-Compliant</option>
              <option value="Needs Review">Needs Review</option>
            </select>
          </div>

          {/* Clear Filters Button */}
          {hasActiveFilters && (
            <button
              type="button"
              onClick={onClearFilters}
              className="inline-flex items-center gap-1.5 rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-xs font-semibold text-rose-700 transition hover:bg-rose-100"
            >
              <RotateCcw className="h-3.5 w-3.5" />
              Clear filters
            </button>
          )}

          {/* Count Badge */}
          <div className="ml-auto flex items-center gap-2 border-l border-slate-200 pl-3 sm:ml-0">
            <Filter className="h-3.5 w-3.5 text-slate-400" />
            <span className="text-xs font-medium text-slate-600">
              Showing <span className="font-bold text-slate-900">{filteredCount}</span> of {totalCount} workers
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default WorkerFilterBar;

