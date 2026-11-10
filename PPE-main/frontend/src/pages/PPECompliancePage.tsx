import { useState, useEffect, useCallback, useMemo } from 'react';
import {
  ShieldCheck,
  CheckCircle2,
  ShieldAlert,
  AlertTriangle,
  RefreshCw,
  PowerOff,
} from 'lucide-react';
import PageHeader from '@/components/PageHeader';
import KpiCard from '@/components/KpiCard';
import ComplianceDistributionChart from '@/components/ComplianceDistributionChart';
import CategoryComparisonChart from '@/components/CategoryComparisonChart';
import CategoryComplianceCard from '@/components/CategoryComplianceCard';
import WorkerComplianceTable from '@/components/WorkerComplianceTable';
import WorkerDetailModal from '@/components/WorkerDetailModal';
import { monitoringService } from '@/services/monitoringService';
import { modelService } from '@/services/modelService';
import { mapMonitoringWorkerToWorkerItem } from '@/utils/workerMapper';
import type { MonitoringWorkerItem, MonitoringStatusResponse } from '@/types/monitoring';
import type {
  PPECategoryComplianceSummary,
  WorkerComplianceRow,
  ComplianceStandardStatus,
} from '@/types/compliance';
import type { DemoDistributionSlice } from '@/types/overview';
import type { WorkerItem } from '@/types/workers';

export default function PPECompliancePage() {
  const [workers, setWorkers] = useState<MonitoringWorkerItem[]>([]);
  const [status, setStatus] = useState<MonitoringStatusResponse | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [selectedWorker, setSelectedWorker] = useState<WorkerItem | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);

  const [supportedPpe, setSupportedPpe] = useState<string[]>([
    'hardhat',
    'safety_vest',
    'gloves',
    'goggles',
    'mask',
    'safety_shoes',
  ]);

  const fetchData = useCallback(async () => {
    try {
      const [statusRes, workersRes, modelRes] = await Promise.all([
        monitoringService.getStatus().catch(() => null),
        monitoringService.getWorkers().catch(() => null),
        modelService.getModels().catch(() => null),
      ]);
      if (statusRes) setStatus(statusRes);
      if (workersRes) setWorkers(workersRes.workers || []);
      if (modelRes && Array.isArray(modelRes.models)) {
        const active = modelRes.models.find((m) => m.is_active);
        if (active && Array.isArray(active.supported_ppe)) {
          setSupportedPpe(active.supported_ppe);
        }
      }
    } catch {
      // In case backend is offline, preserve empty list
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 2500);
    return () => clearInterval(interval);
  }, [fetchData]);

  const isRunning = status?.is_running ?? false;

  // 1. Overall Summary Metrics
  const summaryMetrics = useMemo(() => {
    const total = workers.length;
    let compliant = 0;
    let nonCompliant = 0;
    let review = 0;

    for (const w of workers) {
      const s = w.overall_status || w.compliance_status;
      if (s === 'compliant') compliant++;
      else if (s === 'non_compliant') nonCompliant++;
      else review++;
    }

    const rate = total > 0 ? Math.round((compliant / total) * 1000) / 10 : 0;

    return {
      overallComplianceRate: rate,
      compliantWorkersCount: compliant,
      nonCompliantWorkersCount: nonCompliant,
      reviewWorkersCount: review,
      totalWorkersCount: total,
    };
  }, [workers]);

  // 2. PPE Category Standards
  const categorySummaries: PPECategoryComplianceSummary[] = useMemo(() => {
    const categories: Array<{
      category: 'Hardhat' | 'Safety Vest' | 'Gloves' | 'Goggles' | 'Mask' | 'Safety Shoes';
      key: 'hardhat' | 'safety_vest' | 'gloves' | 'goggles' | 'mask' | 'safety_shoes';
    }> = [
      { category: 'Hardhat', key: 'hardhat' },
      { category: 'Safety Vest', key: 'safety_vest' },
      { category: 'Gloves', key: 'gloves' },
      { category: 'Goggles', key: 'goggles' },
      { category: 'Mask', key: 'mask' },
      { category: 'Safety Shoes', key: 'safety_shoes' },
    ];

    return categories.map(({ category, key }) => {
      let comp = 0;
      let viol = 0;
      let rev = 0;

      for (const w of workers) {
        const catStatus = w.ppe_status?.[key] || w.categories?.[key]?.status;
        if (catStatus === 'compliant') {
          comp++;
        } else if (catStatus === 'missing' || catStatus === 'violation') {
          viol++;
        } else {
          rev++;
        }
      }

      const total = workers.length;
      const rate = total > 0 ? Math.round((comp / total) * 1000) / 10 : 0;

      return {
        category,
        complianceRate: rate,
        compliantCount: comp,
        violationCount: viol,
        reviewCount: rev,
        totalMonitored: total,
      };
    });
  }, [workers]);

  // 3. Compliance Distribution Slices
  const complianceDistribution: DemoDistributionSlice[] = useMemo(() => {
    if (workers.length === 0) return [];
    return [
      { name: 'Compliant', value: summaryMetrics.compliantWorkersCount, tone: 'green' },
      { name: 'Non-Compliant', value: summaryMetrics.nonCompliantWorkersCount, tone: 'red' },
      { name: 'Needs Review', value: summaryMetrics.reviewWorkersCount, tone: 'amber' },
    ];
  }, [workers.length, summaryMetrics]);

  // 4. PPE Category Comparison Bar Chart Data
  const categoryComparison = useMemo(() => {
    return categorySummaries.map((cat) => ({
      category: cat.category,
      compliant: cat.compliantCount,
      violations: cat.violationCount,
      needsReview: cat.reviewCount,
    }));
  }, [categorySummaries]);

  // 5. Worker Compliance Table Rows
  const workerComplianceRows: WorkerComplianceRow[] = useMemo(() => {
    const isCategoryVerifiable = (catKey: string): boolean => {
      return supportedPpe.some((p) => p.toLowerCase().includes(catKey.replace('_', '')) || p.toLowerCase().includes(catKey));
    };

    const toStandardStatus = (catKey: string, val?: string): ComplianceStandardStatus => {
      if (!isCategoryVerifiable(catKey)) {
        return 'Not Verifiable';
      }
      const lower = (val || '').toLowerCase();
      if (lower === 'compliant') return 'Compliant';
      if (lower === 'missing' || lower === 'violation') return 'Non-Compliant';
      if (lower === 'uncertain') return 'Uncertain';
      return 'Needs Review';
    };

    const toOverallStatus = (val?: string): ComplianceStandardStatus => {
      const lower = (val || '').toLowerCase();
      if (lower === 'compliant') return 'Compliant';
      if (lower === 'non_compliant') return 'Non-Compliant';
      return 'Needs Review';
    };

    return workers.map((w) => ({
      workerId: w.worker_track_id,
      name: `Worker #${w.worker_track_id.toString().padStart(2, '0')}`,
      role: 'Tracked Personnel (ByteTrack)',
      zone: 'Live Camera View',
      firstSeen: 'Current session',
      lastSeen: 'Live in view',
      hardhat: toStandardStatus('hardhat', w.ppe_status?.hardhat || w.categories?.hardhat?.status),
      safetyVest: toStandardStatus('safety_vest', w.ppe_status?.safety_vest || w.categories?.safety_vest?.status),
      gloves: toStandardStatus('gloves', w.ppe_status?.gloves || w.categories?.gloves?.status),
      goggles: toStandardStatus('goggles', w.ppe_status?.goggles || w.categories?.goggles?.status),
      mask: toStandardStatus('mask', w.ppe_status?.mask || w.categories?.mask?.status),
      safetyShoes: toStandardStatus('safety_shoes', w.ppe_status?.safety_shoes || w.categories?.safety_shoes?.status),
      overallStatus: toOverallStatus(w.overall_status || w.compliance_status),
    }));
  }, [workers, supportedPpe]);

  const handleSelectWorker = (workerId: number) => {
    const target = workers.find((w) => w.worker_track_id === workerId);
    if (target) {
      setSelectedWorker(mapMonitoringWorkerToWorkerItem(target));
      setIsModalOpen(true);
    }
  };

  const handleCloseModal = () => {
    setIsModalOpen(false);
  };

  return (
    <div className="space-y-6">
      {/* 1. Page Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <PageHeader
          title="PPE Compliance"
          description="Real-time personal protective equipment compliance evaluated across active monitored personnel."
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
            {isRunning ? 'Camera Monitoring Active' : 'Camera Stopped'}
          </div>
          <button
            type="button"
            onClick={fetchData}
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
                Live compliance metrics reflect current detection sessions. Start monitoring from the Live Camera page to stream real-time PPE data.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* 2. Compliance Summary Cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <KpiCard
          label="Overall Compliance Rate"
          value={`${summaryMetrics.overallComplianceRate}%`}
          hint={
            summaryMetrics.totalWorkersCount > 0
              ? `${summaryMetrics.compliantWorkersCount} of ${summaryMetrics.totalWorkersCount} workers compliant`
              : 'No workers currently evaluated'
          }
          icon={ShieldCheck}
          tone="blue"
        />
        <KpiCard
          label="Compliant Workers"
          value={summaryMetrics.compliantWorkersCount.toString()}
          hint="All required PPE standards satisfied"
          icon={CheckCircle2}
          tone="green"
        />
        <KpiCard
          label="Non-Compliant Workers"
          value={summaryMetrics.nonCompliantWorkersCount.toString()}
          hint="Active missing gear or violations"
          icon={ShieldAlert}
          tone="red"
        />
        <KpiCard
          label="Workers Requiring Review"
          value={summaryMetrics.reviewWorkersCount.toString()}
          hint="Uncertain or occluded gear"
          icon={AlertTriangle}
          tone="amber"
        />
      </div>

      {/* 3. PPE Category Compliance (6 standards) */}
      <div>
        <div className="mb-3 flex items-center justify-between">
          <div>
            <h3 className="text-base font-bold text-slate-900">PPE Category Standards</h3>
            <p className="text-xs text-slate-500">
              Live safety compliance rates across 6 mandatory protective equipment categories.
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {categorySummaries.map((categoryData) => (
            <CategoryComplianceCard key={categoryData.category} data={categoryData} />
          ))}
        </div>
      </div>

      {/* 4. Compliance Charts */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <div className="lg:col-span-1">
          <ComplianceDistributionChart data={complianceDistribution} />
        </div>
        <div className="lg:col-span-2">
          <CategoryComparisonChart data={categoryComparison} />
        </div>
      </div>

      {/* 5. Worker Compliance Table */}
      <WorkerComplianceTable
        rows={workerComplianceRows}
        onSelectWorker={handleSelectWorker}
      />

      {/* Worker Detail Inspection Modal */}
      <WorkerDetailModal
        worker={selectedWorker}
        open={isModalOpen}
        onClose={handleCloseModal}
      />
    </div>
  );
}
