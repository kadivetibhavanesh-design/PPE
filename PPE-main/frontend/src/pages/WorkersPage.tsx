import { useState, useMemo, useEffect, useCallback } from 'react';
import { Users, UserCheck, ShieldAlert, ShieldCheck } from 'lucide-react';
import PageHeader from '@/components/PageHeader';
import KpiCard from '@/components/KpiCard';
import WorkerFilterBar from '@/components/WorkerFilterBar';
import WorkerDirectoryTable from '@/components/WorkerDirectoryTable';
import WorkerDetailModal from '@/components/WorkerDetailModal';
import { monitoringService } from '@/services/monitoringService';
import { mapMonitoringWorkerToWorkerItem } from '@/utils/workerMapper';
import type { MonitoringStatusResponse } from '@/types/monitoring';
import type {
  WorkerItem,
  WorkerTrackingStatus,
  WorkerComplianceStatus,
} from '@/types/workers';

export default function WorkersPage() {
  const [workers, setWorkers] = useState<WorkerItem[]>([]);
  const [status, setStatus] = useState<MonitoringStatusResponse | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [trackingFilter, setTrackingFilter] = useState<'All' | WorkerTrackingStatus>('All');
  const [complianceFilter, setComplianceFilter] = useState<'All' | WorkerComplianceStatus>('All');
  const [selectedWorker, setSelectedWorker] = useState<WorkerItem | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);

  const fetchWorkers = useCallback(async () => {
    try {
      const [workersRes, statusRes] = await Promise.all([
        monitoringService.getWorkers().catch(() => null),
        monitoringService.getStatus().catch(() => null),
      ]);

      if (statusRes) setStatus(statusRes);
      if (workersRes && Array.isArray(workersRes.workers)) {
        setWorkers(workersRes.workers.map(mapMonitoringWorkerToWorkerItem));
      } else {
        setWorkers([]);
      }
    } catch (err) {
      console.error('Failed to load workers:', err);
      setWorkers([]);
    }
  }, []);

  useEffect(() => {
    fetchWorkers();
    const interval = setInterval(fetchWorkers, 3000);
    return () => clearInterval(interval);
  }, [fetchWorkers]);

  const isRunning = status?.is_running ?? false;

  // Real KPI metrics from actual tracked workers
  const summaryMetrics = useMemo(() => {
    const totalWorkers = workers.length;
    const activeCount = workers.filter((w) => w.trackingStatus === 'Active').length;
    const compliantCount = workers.filter((w) => w.complianceStatus === 'Compliant').length;
    const nonCompliantCount = workers.filter((w) => w.complianceStatus === 'Non-Compliant').length;
    const complianceRate = activeCount > 0 ? Math.round((compliantCount / activeCount) * 100) : 0;

    return {
      totalWorkers,
      activeCount,
      compliantCount,
      nonCompliantCount,
      complianceRate,
    };
  }, [workers]);

  // Filtered workers list based on user inputs
  const filteredWorkers = useMemo(() => {
    const q = searchQuery.trim().toLowerCase().replace(/^worker\s*#?|^#/, '');

    return workers.filter((worker) => {
      // 1. Search filter (ID or name)
      if (q) {
        const idMatch = worker.workerId.toString() === q || worker.workerId.toString().includes(q);
        const nameMatch = worker.name.toLowerCase().includes(q);
        if (!idMatch && !nameMatch) {
          return false;
        }
      }

      // 2. Tracking status filter
      if (trackingFilter !== 'All' && worker.trackingStatus !== trackingFilter) {
        return false;
      }

      // 3. Compliance status filter
      if (complianceFilter !== 'All' && worker.complianceStatus !== complianceFilter) {
        return false;
      }

      return true;
    });
  }, [workers, searchQuery, trackingFilter, complianceFilter]);

  const handleClearFilters = () => {
    setSearchQuery('');
    setTrackingFilter('All');
    setComplianceFilter('All');
  };

  const handleSelectWorker = (worker: WorkerItem) => {
    setSelectedWorker(worker);
    setIsModalOpen(true);
  };

  const handleCloseModal = () => {
    setIsModalOpen(false);
  };

  const statusLabel = isRunning
    ? `Monitoring Active (${status?.current_fps?.toFixed(1) || 0} FPS)`
    : 'Camera Offline';

  return (
    <div className="space-y-6">
      {/* 1. Page Header */}
      <PageHeader
        title="Worker Directory"
        description="Real-time personnel tracking, ByteTrack persistent IDs, and PPE safety profiles."
        statusLabel={statusLabel}
      />

      {/* 2. Summary KPI Cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <KpiCard
          label="Tracked Workers"
          value={String(summaryMetrics.totalWorkers)}
          hint={isRunning ? 'Active tracked individuals' : 'Camera stopped'}
          icon={Users}
          tone="blue"
        />
        <KpiCard
          label="In Camera View"
          value={String(summaryMetrics.activeCount)}
          hint="Currently in frame"
          icon={UserCheck}
          tone="blue"
        />
        <KpiCard
          label="Compliant Personnel"
          value={String(summaryMetrics.compliantCount)}
          hint={`${summaryMetrics.compliantCount} of ${summaryMetrics.activeCount || 0} compliant`}
          icon={ShieldCheck}
          tone="green"
        />
        <KpiCard
          label="Active Violations"
          value={String(summaryMetrics.nonCompliantCount)}
          hint={summaryMetrics.nonCompliantCount > 0 ? 'Safety violations active' : 'Zero violations'}
          icon={ShieldAlert}
          tone={summaryMetrics.nonCompliantCount > 0 ? 'red' : 'green'}
        />
      </div>

      {/* 3. Search and Filters */}
      <WorkerFilterBar
        searchQuery={searchQuery}
        trackingFilter={trackingFilter}
        complianceFilter={complianceFilter}
        onSearchChange={setSearchQuery}
        onTrackingFilterChange={setTrackingFilter}
        onComplianceFilterChange={setComplianceFilter}
        onClearFilters={handleClearFilters}
        totalCount={workers.length}
        filteredCount={filteredWorkers.length}
      />

      {/* 4. Directory Table */}
      <WorkerDirectoryTable
        workers={filteredWorkers}
        onSelectWorker={handleSelectWorker}
        hasFilters={searchQuery !== '' || trackingFilter !== 'All' || complianceFilter !== 'All'}
        onResetFilters={handleClearFilters}
      />

      {/* 5. Detail Modal */}
      <WorkerDetailModal
        worker={selectedWorker}
        open={isModalOpen}
        onClose={handleCloseModal}
      />
    </div>
  );
}
