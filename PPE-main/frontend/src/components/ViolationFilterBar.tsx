import React from 'react';
import { Search, X, Filter, RotateCcw } from 'lucide-react';
import type { PPEStandardCategory } from '@/types/compliance';
import type { ViolationSeverityLevel, ViolationLifecycleStatus } from '@/types/violations';

interface ViolationFilterBarProps {
  searchQuery: string;
  onSearchChange: (value: string) => void;
  categoryFilter: 'All' | PPEStandardCategory;
  onCategoryFilterChange: (value: 'All' | PPEStandardCategory) => void;
  severityFilter: 'All' | ViolationSeverityLevel;
  onSeverityFilterChange: (value: 'All' | ViolationSeverityLevel) => void;
  statusFilter: 'All' | ViolationLifecycleStatus;
  onStatusFilterChange: (value: 'All' | ViolationLifecycleStatus) => void;
  dateFrom?: string;
  onDateFromChange?: (value: string) => void;
  dateTo?: string;
  onDateToChange?: (value: string) => void;
  onClearFilters: () => void;
  totalCount: number;
  filteredCount: number;
}

export const ViolationFilterBar: React.FC<ViolationFilterBarProps> = ({
  searchQuery,
  onSearchChange,
  categoryFilter,
  onCategoryFilterChange,
  severityFilter,
  onSeverityFilterChange,
  statusFilter,
  onStatusFilterChange,
  dateFrom = '',
  onDateFromChange,
  dateTo = '',
  onDateToChange,
  onClearFilters,
  totalCount,
  filteredCount,
}) => {
  const hasActiveFilters =
    searchQuery.trim().length > 0 ||
    categoryFilter !== 'All' ||
    severityFilter !== 'All' ||
    statusFilter !== 'All' ||
    Boolean(dateFrom) ||
    Boolean(dateTo);

  return (
    <div className="glass-card rounded-2xl p-4 sm:p-5">
      <div className="flex flex-col gap-4">
        {/* Row 1: Search Input */}
        <div className="relative w-full">
          <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3.5 text-slate-400">
            <Search className="h-4 w-4" />
          </div>
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => onSearchChange(e.target.value)}
            placeholder="Search by worker tracking ID (e.g. 1) or incident ID (e.g. EVT-0001)..."
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

        {/* Row 2: Select Filters and Actions */}
        <div className="flex flex-wrap items-center gap-3">
          {/* Category Filter */}
          <div className="flex items-center gap-1.5">
            <label htmlFor="category-filter" className="text-xs font-medium text-slate-500">
              Category:
            </label>
            <select
              id="category-filter"
              value={categoryFilter}
              onChange={(e) => onCategoryFilterChange(e.target.value as 'All' | PPEStandardCategory)}
              className="rounded-xl border border-slate-200 bg-white/80 px-3 py-2 text-xs font-semibold text-slate-700 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20"
            >
              <option value="All">All Categories</option>
              <option value="Hardhat">Hardhat</option>
              <option value="Safety Vest">Safety Vest</option>
              <option value="Gloves">Gloves</option>
              <option value="Goggles">Goggles</option>
              <option value="Mask">Mask</option>
              <option value="Safety Shoes">Safety Shoes</option>
            </select>
          </div>

          {/* Severity Filter */}
          <div className="flex items-center gap-1.5">
            <label htmlFor="severity-filter" className="text-xs font-medium text-slate-500">
              Severity:
            </label>
            <select
              id="severity-filter"
              value={severityFilter}
              onChange={(e) => onSeverityFilterChange(e.target.value as 'All' | ViolationSeverityLevel)}
              className="rounded-xl border border-slate-200 bg-white/80 px-3 py-2 text-xs font-semibold text-slate-700 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20"
            >
              <option value="All">All Severities</option>
              <option value="Critical">Critical</option>
              <option value="High">High</option>
              <option value="Medium">Medium</option>
            </select>
          </div>

          {/* Status Filter */}
          <div className="flex items-center gap-1.5">
            <label htmlFor="status-filter" className="text-xs font-medium text-slate-500">
              Status:
            </label>
            <select
              id="status-filter"
              value={statusFilter}
              onChange={(e) => onStatusFilterChange(e.target.value as 'All' | ViolationLifecycleStatus)}
              className="rounded-xl border border-slate-200 bg-white/80 px-3 py-2 text-xs font-semibold text-slate-700 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20"
            >
              <option value="All">All Statuses</option>
              <option value="Open">Open</option>
              <option value="Ongoing">Ongoing</option>
              <option value="Resolved">Resolved</option>
              <option value="Closed">Closed</option>
            </select>
          </div>

          {/* Date range filters */}
          {onDateFromChange && (
            <div className="flex items-center gap-1.5">
              <label htmlFor="date-from" className="text-xs font-medium text-slate-500">
                From:
              </label>
              <input
                id="date-from"
                type="date"
                value={dateFrom}
                onChange={(e) => onDateFromChange(e.target.value)}
                className="rounded-xl border border-slate-200 bg-white/80 px-2.5 py-1.5 text-xs font-medium text-slate-700 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20"
              />
            </div>
          )}

          {onDateToChange && (
            <div className="flex items-center gap-1.5">
              <label htmlFor="date-to" className="text-xs font-medium text-slate-500">
                To:
              </label>
              <input
                id="date-to"
                type="date"
                value={dateTo}
                onChange={(e) => onDateToChange(e.target.value)}
                className="rounded-xl border border-slate-200 bg-white/80 px-2.5 py-1.5 text-xs font-medium text-slate-700 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20"
              />
            </div>
          )}

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

          {/* Match Counter */}
          <div className="ml-auto flex items-center gap-2 border-l border-slate-200 pl-3 sm:ml-0">
            <Filter className="h-3.5 w-3.5 text-slate-400" />
            <span className="text-xs font-medium text-slate-600">
              Showing <span className="font-bold text-slate-900">{filteredCount}</span> of {totalCount} violations
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ViolationFilterBar;

