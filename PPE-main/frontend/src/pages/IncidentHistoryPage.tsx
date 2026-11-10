import { useState, useEffect, useMemo, useCallback } from 'react';
import {
  AlertTriangle,
  CheckCircle2,
  Camera,
  RefreshCw,
  FolderArchive,
  PowerOff,
} from 'lucide-react';
import PageHeader from '@/components/PageHeader';
import KpiCard from '@/components/KpiCard';
import IncidentFilterBar from '@/components/IncidentFilterBar';
import IncidentHistoryTable from '@/components/IncidentHistoryTable';
import IncidentDetailsModal from '@/components/IncidentDetailsModal';
import { evidenceService } from '@/services/evidenceService';
import type { EvidenceRecord } from '@/types/evidence';

export default function IncidentHistoryPage() {
  const [evidenceList, setEvidenceList] = useState<EvidenceRecord[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Filters state
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [severityFilter, setSeverityFilter] = useState<string>('All');
  const [categoryFilter, setCategoryFilter] = useState<string>('All');
  const [statusFilter, setStatusFilter] = useState<string>('All');
  const [dateFrom, setDateFrom] = useState<string>('');
  const [dateTo, setDateTo] = useState<string>('');

  // Pagination state
  const [currentPage, setCurrentPage] = useState<number>(1);
  const [pageSize, setPageSize] = useState<number>(10);

  // Selected item for detail modal
  const [selectedEvidence, setSelectedEvidence] = useState<EvidenceRecord | null>(null);
  const [isModalOpen, setIsModalOpen] = useState<boolean>(false);

  /**
   * Refreshes real incident evidence records from the backend.
   */
  const handleRefresh = useCallback(async () => {
    setIsRefreshing(true);
    setErrorMessage(null);
    try {
      const records = await evidenceService.getEvidenceList();
      setEvidenceList(records);
    } catch (err: unknown) {
      const msg =
        err instanceof Error
          ? err.message
          : 'Failed to connect to local evidence storage service.';
      setErrorMessage(msg);
      console.error('[IncidentHistory] Error loading evidence records:', err);
    } finally {
      setIsRefreshing(false);
    }
  }, []);

  // Initial load on mount
  useEffect(() => {
    let isMounted = true;
    evidenceService
      .getEvidenceList()
      .then((records) => {
        if (isMounted) {
          setEvidenceList(records);
          setIsLoading(false);
        }
      })
      .catch((err: unknown) => {
        if (isMounted) {
          const msg =
            err instanceof Error
              ? err.message
              : 'Failed to connect to local evidence storage service.';
          setErrorMessage(msg);
          setIsLoading(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, []);

  // Dynamic KPI summary metrics derived directly from real evidence
  const metrics = useMemo(() => {
    const totalCount = evidenceList.length;
    let activeCount = 0;
    let resolvedCount = 0;
    let interruptedCount = 0;
    let withImageCount = 0;

    for (const item of evidenceList) {
      const st = (item.status || item.event_status || '').toLowerCase();
      if (st === 'open' || st === 'ongoing') {
        activeCount += 1;
      } else if (st === 'resolved' || st === 'closed') {
        resolvedCount += 1;
      } else if (st === 'interrupted') {
        interruptedCount += 1;
      }
      if (item.image_filename || item.evidence_image_filename) {
        withImageCount += 1;
      }
    }

    return { totalCount, activeCount, resolvedCount, interruptedCount, withImageCount };
  }, [evidenceList]);

  // Client-side filtering logic
  const filteredEvidence = useMemo(() => {
    const q = searchQuery.trim().toLowerCase().replace(/^worker\s*#?|^#/, '');

    return evidenceList.filter((item) => {
      // 1. Search Query: matches event_id or worker_track_id
      if (q) {
        const eventIdMatch = item.event_id.toLowerCase().includes(q);
        const workerIdMatch = item.worker_track_id.toString().includes(q);
        const categoryMatch = item.ppe_category.toLowerCase().includes(q);
        if (!eventIdMatch && !workerIdMatch && !categoryMatch) {
          return false;
        }
      }

      // 2. Severity filter
      if (severityFilter !== 'All') {
        if ((item.severity || '').toLowerCase() !== severityFilter.toLowerCase()) {
          return false;
        }
      }

      // 3. Category filter
      if (categoryFilter !== 'All') {
        const itemCat = item.ppe_category.toLowerCase().replace(/[\s-]/g, '_');
        const filterCat = categoryFilter.toLowerCase().replace(/[\s-]/g, '_');
        if (itemCat !== filterCat) {
          return false;
        }
      }

      // 4. Status filter
      if (statusFilter !== 'All') {
        const st = (item.status || item.event_status || '').toLowerCase();
        if (st !== statusFilter.toLowerCase()) {
          return false;
        }
      }

      // 5. Date From filter
      if (dateFrom && item.first_detected_timestamp) {
        const fromTs = new Date(`${dateFrom}T00:00:00`).getTime();
        const eventTs = item.first_detected_timestamp < 1e11 ? item.first_detected_timestamp * 1000 : item.first_detected_timestamp;
        if (eventTs < fromTs) {
          return false;
        }
      }

      // 6. Date To filter
      if (dateTo && item.first_detected_timestamp) {
        const toTs = new Date(`${dateTo}T23:59:59`).getTime();
        const eventTs = item.first_detected_timestamp < 1e11 ? item.first_detected_timestamp * 1000 : item.first_detected_timestamp;
        if (eventTs > toTs) {
          return false;
        }
      }

      return true;
    });
  }, [evidenceList, searchQuery, severityFilter, categoryFilter, statusFilter, dateFrom, dateTo]);

  const totalPages = Math.max(1, Math.ceil(filteredEvidence.length / pageSize));

  // Auto-clamp page if filter narrows results
  useEffect(() => {
    setCurrentPage(1);
  }, [searchQuery, severityFilter, categoryFilter, statusFilter, dateFrom, dateTo, pageSize]);

  const paginatedEvidence = useMemo(() => {
    const start = (currentPage - 1) * pageSize;
    return filteredEvidence.slice(start, start + pageSize);
  }, [filteredEvidence, currentPage, pageSize]);

  const isFiltered =
    Boolean(searchQuery.trim()) ||
    severityFilter !== 'All' ||
    categoryFilter !== 'All' ||
    statusFilter !== 'All' ||
    Boolean(dateFrom) ||
    Boolean(dateTo);

  const handleClearFilters = () => {
    setSearchQuery('');
    setSeverityFilter('All');
    setCategoryFilter('All');
    setStatusFilter('All');
    setDateFrom('');
    setDateTo('');
    setCurrentPage(1);
  };

  const handleSelectEvidence = (item: EvidenceRecord) => {
    setSelectedEvidence(item);
    setIsModalOpen(true);
  };

  const handleCloseModal = () => {
    setIsModalOpen(false);
  };

  return (
    <div className="space-y-6">
      {/* Top Page Header */}
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <PageHeader
          title="Incident History"
          description="Local audit trail of confirmed PPE safety violations, captured camera frames, and resolution timestamps."
          statusLabel="Evidence Storage Active"
        />
        <div className="flex items-center gap-3">
          <button
            onClick={handleRefresh}
            disabled={isLoading || isRefreshing}
            className="glass-card inline-flex items-center gap-2 rounded-xl px-4 py-2.5 text-xs font-semibold text-slate-700 shadow-sm transition hover:bg-slate-50 hover:text-slate-900 disabled:opacity-50"
            title="Refresh incident evidence records from backend"
          >
            <RefreshCw
              className={`h-3.5 w-3.5 text-indigo-600 ${
                isRefreshing ? 'animate-spin' : ''
              }`}
            />
            <span>{isRefreshing ? 'Refreshing...' : 'Refresh Records'}</span>
          </button>
        </div>
      </div>

      {/* KPI Metric Cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
        <KpiCard
          label="Total Incidents"
          value={metrics.totalCount.toString()}
          hint="All confirmed events"
          icon={FolderArchive}
          tone="blue"
        />
        <KpiCard
          label="Active Incidents"
          value={metrics.activeCount.toString()}
          hint="Open or ongoing"
          icon={AlertTriangle}
          tone="red"
        />
        <KpiCard
          label="Resolved Incidents"
          value={metrics.resolvedCount.toString()}
          hint="Rectified or closed"
          icon={CheckCircle2}
          tone="green"
        />
        <KpiCard
          label="Interrupted"
          value={metrics.interruptedCount.toString()}
          hint="Camera stopped"
          icon={PowerOff}
          tone="amber"
        />
        <KpiCard
          label="Captured Evidence"
          value={metrics.withImageCount.toString()}
          hint="Saved snapshots"
          icon={Camera}
          tone="amber"
        />
      </div>

      {/* Backend Error State Banner */}
      {errorMessage && (
        <div className="glass-card flex flex-col gap-3 rounded-2xl border-rose-200 bg-rose-50/70 p-5 text-rose-900 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-start gap-3">
            <div className="rounded-xl bg-rose-100 p-2 text-rose-700">
              <AlertTriangle className="h-5 w-5" />
            </div>
            <div>
              <h4 className="text-sm font-bold">Failed to Connect to Evidence Storage</h4>
              <p className="mt-0.5 text-xs text-rose-700">{errorMessage}</p>
              <p className="mt-1 text-[11px] text-rose-600">
                Please ensure the backend service is running and accessible.
              </p>
            </div>
          </div>
          <button
            onClick={handleRefresh}
            className="inline-flex items-center gap-1.5 self-start rounded-xl bg-rose-700 px-3.5 py-2 text-xs font-semibold text-white shadow-sm transition hover:bg-rose-800 sm:self-center"
          >
            <RefreshCw className="h-3.5 w-3.5" />
            <span>Retry Connection</span>
          </button>
        </div>
      )}

      {/* Search and Filters Bar */}
      <IncidentFilterBar
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
        severityFilter={severityFilter}
        onSeverityChange={setSeverityFilter}
        categoryFilter={categoryFilter}
        onCategoryChange={setCategoryFilter}
        statusFilter={statusFilter}
        onStatusChange={setStatusFilter}
        dateFrom={dateFrom}
        onDateFromChange={setDateFrom}
        dateTo={dateTo}
        onDateToChange={setDateTo}
        onClearFilters={handleClearFilters}
        totalResults={evidenceList.length}
        filteredCount={filteredEvidence.length}
      />

      {/* Table / Content State */}
      {isLoading ? (
        <div className="glass-card flex flex-col items-center justify-center rounded-2xl py-16 text-center">
          <div className="h-8 w-8 animate-spin rounded-full border-3 border-indigo-600 border-t-transparent mb-3" />
          <p className="text-sm font-semibold text-slate-800">
            Loading Incident Evidence...
          </p>
          <p className="mt-1 text-xs text-slate-500">
            Querying local evidence repository from FastAPI backend
          </p>
        </div>
      ) : (
        <IncidentHistoryTable
          evidenceList={paginatedEvidence}
          onSelectEvidence={handleSelectEvidence}
          isFiltered={isFiltered}
          onClearFilters={handleClearFilters}
          currentPage={currentPage}
          totalPages={totalPages}
          pageSize={pageSize}
          totalFilteredCount={filteredEvidence.length}
          onPageChange={setCurrentPage}
          onPageSizeChange={setPageSize}
        />
      )}

      {/* Incident Details Modal */}
      <IncidentDetailsModal
        evidence={selectedEvidence}
        open={isModalOpen}
        onClose={handleCloseModal}
      />
    </div>
  );
}
