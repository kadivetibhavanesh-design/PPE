import React from 'react';
import { Search, X, Filter } from 'lucide-react';

interface IncidentFilterBarProps {
  searchQuery: string;
  onSearchChange: (val: string) => void;
  severityFilter: string;
  onSeverityChange: (val: string) => void;
  categoryFilter: string;
  onCategoryChange: (val: string) => void;
  statusFilter: string;
  onStatusChange: (val: string) => void;
  dateFrom?: string;
  onDateFromChange?: (val: string) => void;
  dateTo?: string;
  onDateToChange?: (val: string) => void;
  onClearFilters: () => void;
  totalResults: number;
  filteredCount: number;
}

const SEVERITY_OPTIONS = ['All', 'Critical', 'High', 'Medium', 'Low'];
const CATEGORY_OPTIONS = [
  'All',
  'Hardhat',
  'Safety Vest',
  'Gloves',
  'Goggles',
  'Mask',
  'Safety Shoes',
];
const STATUS_OPTIONS = ['All', 'Open', 'Ongoing', 'Resolved', 'Closed', 'Interrupted'];

export const IncidentFilterBar: React.FC<IncidentFilterBarProps> = ({
  searchQuery,
  onSearchChange,
  severityFilter,
  onSeverityChange,
  categoryFilter,
  onCategoryChange,
  statusFilter,
  onStatusChange,
  dateFrom = '',
  onDateFromChange,
  dateTo = '',
  onDateToChange,
  onClearFilters,
  totalResults,
  filteredCount,
}) => {
  const isFiltered =
    Boolean(searchQuery.trim()) ||
    severityFilter !== 'All' ||
    categoryFilter !== 'All' ||
    statusFilter !== 'All' ||
    Boolean(dateFrom) ||
    Boolean(dateTo);

  return (
    <div className="glass-card rounded-2xl p-4 sm:p-5">
      <div className="flex flex-col gap-3.5 lg:flex-row lg:items-center lg:justify-between">
        {/* Search input */}
        <div className="relative flex-1">
          <Search className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => onSearchChange(e.target.value)}
            placeholder="Search by event ID (e.g. EVT-0001) or worker ID..."
            className="w-full rounded-xl border border-slate-200/90 bg-white/90 py-2.5 pl-10 pr-9 text-sm text-slate-800 placeholder-slate-400 shadow-sm transition-all focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-100"
          />
          {searchQuery && (
            <button
              onClick={() => onSearchChange('')}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
              aria-label="Clear search query"
            >
              <X className="h-4 w-4" />
            </button>
          )}
        </div>

        {/* Dropdown filters */}
        <div className="flex flex-wrap items-center gap-2.5">
          {/* Severity selector */}
          <div className="flex items-center gap-1.5">
            <label htmlFor="severity-filter" className="text-xs font-semibold text-slate-600">
              Severity:
            </label>
            <select
              id="severity-filter"
              value={severityFilter}
              onChange={(e) => onSeverityChange(e.target.value)}
              className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-medium text-slate-700 shadow-sm transition focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-100"
            >
              {SEVERITY_OPTIONS.map((opt) => (
                <option key={opt} value={opt}>
                  {opt}
                </option>
              ))}
            </select>
          </div>

          {/* Category selector */}
          <div className="flex items-center gap-1.5">
            <label htmlFor="category-filter" className="text-xs font-semibold text-slate-600">
              PPE:
            </label>
            <select
              id="category-filter"
              value={categoryFilter}
              onChange={(e) => onCategoryChange(e.target.value)}
              className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-medium text-slate-700 shadow-sm transition focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-100"
            >
              {CATEGORY_OPTIONS.map((opt) => (
                <option key={opt} value={opt}>
                  {opt}
                </option>
              ))}
            </select>
          </div>

          {/* Status selector */}
          <div className="flex items-center gap-1.5">
            <label htmlFor="status-filter" className="text-xs font-semibold text-slate-600">
              Status:
            </label>
            <select
              id="status-filter"
              value={statusFilter}
              onChange={(e) => onStatusChange(e.target.value)}
              className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-medium text-slate-700 shadow-sm transition focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-100"
            >
              {STATUS_OPTIONS.map((opt) => (
                <option key={opt} value={opt}>
                  {opt}
                </option>
              ))}
            </select>
          </div>

          {/* Date range pickers */}
          {onDateFromChange && (
            <div className="flex items-center gap-1.5">
              <label htmlFor="inc-date-from" className="text-xs font-semibold text-slate-600">
                From:
              </label>
              <input
                id="inc-date-from"
                type="date"
                value={dateFrom}
                onChange={(e) => onDateFromChange(e.target.value)}
                className="rounded-xl border border-slate-200 bg-white px-2.5 py-1.5 text-xs font-medium text-slate-700 shadow-sm transition focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-100"
              />
            </div>
          )}

          {onDateToChange && (
            <div className="flex items-center gap-1.5">
              <label htmlFor="inc-date-to" className="text-xs font-semibold text-slate-600">
                To:
              </label>
              <input
                id="inc-date-to"
                type="date"
                value={dateTo}
                onChange={(e) => onDateToChange(e.target.value)}
                className="rounded-xl border border-slate-200 bg-white px-2.5 py-1.5 text-xs font-medium text-slate-700 shadow-sm transition focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-100"
              />
            </div>
          )}

          {/* Clear Filters Button */}
          {isFiltered && (
            <button
              onClick={onClearFilters}
              className="inline-flex items-center gap-1.5 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs font-medium text-slate-700 transition hover:bg-slate-100 hover:text-slate-900"
            >
              <Filter className="h-3.5 w-3.5 text-slate-500" />
              Reset Filters
            </button>
          )}

          {/* Record counter */}
          <span className="ml-auto inline-flex items-center rounded-lg bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-600 lg:ml-0">
            {isFiltered
              ? `Showing ${filteredCount} of ${totalResults}`
              : `${totalResults} ${totalResults === 1 ? 'record' : 'records'}`}
          </span>
        </div>
      </div>
    </div>
  );
};

export default IncidentFilterBar;

