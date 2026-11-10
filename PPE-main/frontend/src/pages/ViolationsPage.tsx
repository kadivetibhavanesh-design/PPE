import { useState, useMemo, useEffect, useCallback } from 'react';
import {
  ShieldAlert,
  AlertTriangle,
  Timer,
  CheckCircle2,
  RefreshCw,
  PowerOff,
} from 'lucide-react';
import PageHeader from '@/components/PageHeader';
import KpiCard from '@/components/KpiCard';
import ViolationFilterBar from '@/components/ViolationFilterBar';
import ViolationRecordsTable from '@/components/ViolationRecordsTable';
import ViolationDetailModal from '@/components/ViolationDetailModal';
import { violationService, type ViolationEvent } from '@/services/violationService';
import { monitoringService } from '@/services/monitoringService';
import { evidenceService } from '@/services/evidenceService';
import type { MonitoringStatusResponse } from '@/types/monitoring';
import type {
  ViolationRecord,
  ViolationSeverityLevel,
  ViolationLifecycleStatus,
} from '@/types/violations';
import type { PPEStandardCategory } from '@/types/compliance';

function mapEventToRecord(
  event: ViolationEvent & { ppe_categories?: string[] },
  evidenceIds: Set<string>
): ViolationRecord {
  const categoryMap: Record<string, PPEStandardCategory> = {
    hardhat: 'Hardhat',
    safety_vest: 'Safety Vest',
    gloves: 'Gloves',
    goggles: 'Goggles',
    mask: 'Mask',
    safety_shoes: 'Safety Shoes',
  };

  const severityMap: Record<string, ViolationSeverityLevel> = {
    critical: 'Critical',
    high: 'High',
    medium: 'Medium',
  };

  const statusMap: Record<string, ViolationLifecycleStatus> = {
    open: 'Open',
    ongoing: 'Ongoing',
    resolved: 'Resolved',
    closed: 'Closed',
    interrupted: 'Closed',
  };

  const ppeCategory = categoryMap[event.ppe_category?.toLowerCase()] || 'Hardhat';
  const severity = severityMap[event.severity?.toLowerCase()] || 'High';
  const status = statusMap[event.status?.toLowerCase()] || 'Open';

  const dateStr = event.start_timestamp
    ? new Date(event.start_timestamp * 1000).toLocaleString([], {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
      })
    : 'Recently';

  const rawCategories =
    event.ppe_categories ||
    (event.ppe_category ? event.ppe_category.split(',').map((s) => s.trim()) : []);
  const ppeCategories = rawCategories.map((c) => categoryMap[c.toLowerCase()] || c);

  return {
    violationId: event.event_id,
    workerId: event.worker_track_id,
    workerName: `Worker #${event.worker_track_id.toString().padStart(2, '0')}`,
    workerRole: 'ByteTrack Identity',
    workerZone: 'Zone A - Primary Surveillance',
    ppeCategory,
    ppeCategories,
    severity,
    firstDetected: dateStr,
    firstDetectedTimestamp: event.start_timestamp,
    confirmationTimestamp: event.confirmation_timestamp,
    resolutionTimestamp: event.resolution_timestamp ?? undefined,
    durationSeconds: Math.round(event.violation_duration || 0),
    status,
    hasEvidence: evidenceIds.has(event.event_id),
    description: `Continuous missing ${
      ppeCategories.length > 0 ? ppeCategories.join(', ') : ppeCategory
    } detected on tracked Worker #${event.worker_track_id}.`,
  };
}

export default function ViolationsPage() {
  const [violations, setViolations] = useState<ViolationRecord[]>([]);
  const [status, setStatus] = useState<MonitoringStatusResponse | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [categoryFilter, setCategoryFilter] = useState<'All' | PPEStandardCategory>('All');
  const [severityFilter, setSeverityFilter] = useState<'All' | ViolationSeverityLevel>('All');
  const [statusFilter, setStatusFilter] = useState<'All' | ViolationLifecycleStatus>('All');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [selectedViolation, setSelectedViolation] = useState<ViolationRecord | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);

  const fetchViolations = useCallback(async () => {
    try {
      const [statusRes, violationsRes, evidenceRes] = await Promise.all([
        monitoringService.getStatus(),
        violationService.getViolations(),
        evidenceService.getEvidenceList().catch(() => []),
      ]);
      setStatus(statusRes);
      const evidenceIds = new Set((evidenceRes || []).map((e) => e.event_id));
      const mapped = (violationsRes.events || []).map((ev) => mapEventToRecord(ev, evidenceIds));
      setViolations(mapped);
    } catch {
      // Retain existing violations on transient network failure
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchViolations();
    const interval = setInterval(fetchViolations, 2500);
    return () => clearInterval(interval);
  }, [fetchViolations]);

  const isRunning = status?.is_running ?? false;

  // Dynamic metrics based on real violation records
  const metrics = useMemo(() => {
    let active = 0;
    let critical = 0;
    let resolved = 0;

    for (const v of violations) {
      if (v.status === 'Open' || v.status === 'Ongoing') active++;
      if (v.severity === 'Critical') critical++;
      if (v.status === 'Resolved' || v.status === 'Closed') resolved++;
    }

    return {
      totalViolations: violations.length,
      activeViolations: active,
      criticalViolations: critical,
      resolvedViolations: resolved,
    };
  }, [violations]);

  // Client-side filtering logic
  const filteredViolations = useMemo(() => {
    const q = searchQuery.trim().toLowerCase().replace(/^worker\s*#?|^#/, '');

    return violations.filter((v) => {
      // 1. Search filter: worker ID, name, or violation ID
      if (q) {
        const idMatch = v.workerId.toString() === q || v.workerId.toString().includes(q);
        const nameMatch = v.workerName.toLowerCase().includes(q);
        const vioIdMatch = v.violationId.toLowerCase().includes(q);
        const roleMatch = v.workerRole.toLowerCase().includes(q);
        if (!idMatch && !nameMatch && !vioIdMatch && !roleMatch) {
          return false;
        }
      }

      // 2. PPE Category filter
      if (categoryFilter !== 'All') {
        const hasCategory =
          v.ppeCategory === categoryFilter ||
          (v.ppeCategories && v.ppeCategories.includes(categoryFilter));
        if (!hasCategory) return false;
      }

      // 3. Severity filter
      if (severityFilter !== 'All' && v.severity !== severityFilter) {
        return false;
      }

      // 4. Status filter
      if (statusFilter !== 'All' && v.status !== statusFilter) {
        return false;
      }

      // 5. Date From filter
      if (dateFrom && v.firstDetectedTimestamp) {
        const fromTs = new Date(`${dateFrom}T00:00:00`).getTime();
        if (v.firstDetectedTimestamp * 1000 < fromTs) {
          return false;
        }
      }

      // 6. Date To filter
      if (dateTo && v.firstDetectedTimestamp) {
        const toTs = new Date(`${dateTo}T23:59:59`).getTime();
        if (v.firstDetectedTimestamp * 1000 > toTs) {
          return false;
        }
      }

      return true;
    });
  }, [violations, searchQuery, categoryFilter, severityFilter, statusFilter, dateFrom, dateTo]);

  const handleClearFilters = () => {
    setSearchQuery('');
    setCategoryFilter('All');
    setSeverityFilter('All');
    setStatusFilter('All');
    setDateFrom('');
    setDateTo('');
  };

  const handleSelectViolation = (violation: ViolationRecord) => {
    setSelectedViolation(violation);
    setIsModalOpen(true);
  };

  const handleCloseModal = () => {
    setIsModalOpen(false);
  };

  const handleResolveViolation = async (violationId: string) => {
    try {
      await violationService.resolveViolation(violationId);
    } catch (err) {
      console.error('Failed to resolve violation on backend:', err);
    }
    setViolations((prev) =>
      prev.map((item) =>
        item.violationId === violationId ? { ...item, status: 'Resolved' } : item
      )
    );
    setSelectedViolation((prev) =>
      prev && prev.violationId === violationId ? { ...prev, status: 'Resolved' } : prev
    );
  };

  const hasActiveFilters =
    searchQuery.trim().length > 0 ||
    categoryFilter !== 'All' ||
    severityFilter !== 'All' ||
    statusFilter !== 'All' ||
    Boolean(dateFrom) ||
    Boolean(dateTo);

  return (
    <div className="space-y-6">
      {/* 1. Page Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <PageHeader
          title="Violations"
          description="Review and manage detected industrial PPE violations from the active surveillance session."
        />
        <div className="flex items-center gap-3">
          <div
            className={`inline-flex items-center gap-2 rounded-xl px-3.5 py-1.5 text-xs font-semibold shadow-xs ${
              isRunning
                ? 'border border-emerald-200 bg-emerald-50 text-emerald-700'
                : 'border border-slate-200 bg-slate-100 text-slate-600'
            }`}
          >
            <span
              className={`h-2 w-2 rounded-full ${
                isRunning ? 'bg-emerald-500 animate-pulse' : 'bg-slate-400'
              }`}
            />
            {isRunning ? 'Surveillance Active' : 'Camera Stopped'}
          </div>
          <button
            type="button"
            onClick={fetchViolations}
            disabled={isLoading}
            className="inline-flex items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-3.5 py-1.5 text-xs font-semibold text-slate-700 shadow-xs transition hover:border-slate-300 hover:bg-slate-50"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${isLoading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>
      </div>

      {/* Camera Inactive Notice if stopped */}
      {!isRunning && (
        <div className="flex items-center justify-between rounded-2xl border border-amber-200 bg-amber-50/70 p-4 text-amber-800">
          <div className="flex items-center gap-3">
            <PowerOff className="h-5 w-5 text-amber-600" />
            <div>
              <p className="text-sm font-semibold">Surveillance Camera Offline</p>
              <p className="text-xs text-amber-700">
                Violations are logged during active camera monitoring sessions when non-compliance persists for 5+ seconds.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* 2. Violation Summary Cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <KpiCard
          label="Total Violations"
          value={metrics.totalViolations.toString()}
          hint="Recorded in session"
          icon={ShieldAlert}
          tone="blue"
        />
        <KpiCard
          label="Active Violations"
          value={metrics.activeViolations.toString()}
          hint="Open or ongoing alerts"
          icon={Timer}
          tone="red"
        />
        <KpiCard
          label="Critical Violations"
          value={metrics.criticalViolations.toString()}
          hint="High-risk safety hazards"
          icon={AlertTriangle}
          tone="red"
        />
        <KpiCard
          label="Resolved Violations"
          value={metrics.resolvedViolations.toString()}
          hint="Closed or rectified events"
          icon={CheckCircle2}
          tone="green"
        />
      </div>

      {/* 3. Violation Filters */}
      <ViolationFilterBar
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
        categoryFilter={categoryFilter}
        onCategoryFilterChange={setCategoryFilter}
        severityFilter={severityFilter}
        onSeverityFilterChange={setSeverityFilter}
        statusFilter={statusFilter}
        onStatusFilterChange={setStatusFilter}
        dateFrom={dateFrom}
        onDateFromChange={setDateFrom}
        dateTo={dateTo}
        onDateToChange={setDateTo}
        onClearFilters={handleClearFilters}
        totalCount={violations.length}
        filteredCount={filteredViolations.length}
      />

      {/* 4. Violation Records Table */}
      <ViolationRecordsTable
        violations={filteredViolations}
        onSelectViolation={handleSelectViolation}
        onResetFilters={handleClearFilters}
        hasFilters={hasActiveFilters}
      />

      {/* 5. Violation Detail Modal with Resolve action */}
      <ViolationDetailModal
        violation={selectedViolation}
        open={isModalOpen}
        onClose={handleCloseModal}
        onResolve={handleResolveViolation}
      />
    </div>
  );
}
