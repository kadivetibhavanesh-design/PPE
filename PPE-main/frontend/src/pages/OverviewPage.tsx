import { useState, useEffect, useCallback, useMemo } from 'react';
import {
  Users,
  UserCheck,
  UserX,
  AlertCircle,
  ShieldCheck,
  ShieldAlert,
  TriangleAlert,
  CalendarClock,
  RefreshCw,
  Server,
  Camera,
  Cpu,
  Layers,
} from 'lucide-react';
import KpiCard from '@/components/KpiCard';
import MonitoringSummary from '@/components/MonitoringSummary';
import ComplianceDistributionChart from '@/components/ComplianceDistributionChart';
import ViolationCategoriesChart from '@/components/ViolationCategoriesChart';
import RecentViolationsTable from '@/components/RecentViolationsTable';
import { monitoringService } from '@/services/monitoringService';
import { violationService } from '@/services/violationService';
import { systemService } from '@/services/systemService';
import { evidenceService } from '@/services/evidenceService';
import { modelService } from '@/services/modelService';
import type { MonitoringStatusResponse, ComplianceSummaryResponse } from '@/types/monitoring';
import type { ViolationEvent, ViolationSummaryResponse } from '@/services/violationService';
import type { DemoViolation, DemoCategoryCount, DemoDistributionSlice } from '@/types/overview';
import type { EvidenceRecord } from '@/types/evidence';

export default function OverviewPage() {
  const [lastUpdated, setLastUpdated] = useState(() => new Date());
  const [isBackendOnline, setIsBackendOnline] = useState<boolean>(true);
  const [status, setStatus] = useState<MonitoringStatusResponse | null>(null);
  const [compliance, setCompliance] = useState<ComplianceSummaryResponse | null>(null);
  const [recentEvents, setRecentEvents] = useState<ViolationEvent[]>([]);
  const [violationSummary, setViolationSummary] = useState<ViolationSummaryResponse | null>(null);
  const [evidenceRecords, setEvidenceRecords] = useState<EvidenceRecord[]>([]);
  const [activeModelName, setActiveModelName] = useState<string>('Constructelligence YOLOv8');
  const [supportedPpe, setSupportedPpe] = useState<string[]>(['hardhat', 'safety_vest', 'gloves', 'goggles', 'mask', 'safety_shoes']);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);

  const fetchOverviewData = useCallback(async () => {
    try {
      const [healthRes, statusRes, complianceRes, violationsRes, summaryRes, evidenceRes, modelRes] = await Promise.all([
        systemService.getHealth().catch(() => null),
        monitoringService.getStatus().catch(() => null),
        monitoringService.getComplianceSummary().catch(() => null),
        violationService.getViolations({ limit: 15 }).catch(() => null),
        violationService.getSummary().catch(() => null),
        evidenceService.getEvidenceList().catch(() => []),
        modelService.getModels().catch(() => null),
      ]);

      setIsBackendOnline(Boolean(healthRes));
      if (statusRes) setStatus(statusRes);
      if (complianceRes) setCompliance(complianceRes);
      if (violationsRes) setRecentEvents(violationsRes.events || []);
      if (summaryRes) setViolationSummary(summaryRes);
      if (Array.isArray(evidenceRes)) setEvidenceRecords(evidenceRes);

      if (modelRes && Array.isArray(modelRes.models)) {
        const activeM = modelRes.models.find((m) => m.is_active);
        if (activeM) {
          setActiveModelName(activeM.display_name);
          if (Array.isArray(activeM.supported_ppe)) {
            setSupportedPpe(activeM.supported_ppe);
          }
        }
      }
      setLastUpdated(new Date());
    } catch (err) {
      console.error('Failed to load overview data:', err);
    }
  }, []);

  useEffect(() => {
    fetchOverviewData();
    const interval = setInterval(fetchOverviewData, 4000);
    return () => clearInterval(interval);
  }, [fetchOverviewData]);

  const handleManualRefresh = async () => {
    setIsRefreshing(true);
    await fetchOverviewData();
    setIsRefreshing(false);
  };

  // Derive real telemetry metrics without inventing numbers
  const isRunning = status?.is_running ?? false;
  const monitoringState = isRunning ? 'Active' : status?.status === 'starting' ? 'Starting' : 'Idle';
  const cameraState = isRunning ? 'Active' : 'Offline';
  const activeWorkers = status?.active_workers_count ?? 0;
  const compliantWorkers = status?.compliant_workers_count ?? compliance?.compliant_workers ?? 0;
  const nonCompliantWorkers = status?.non_compliant_workers_count ?? compliance?.non_compliant_workers ?? 0;
  const reviewWorkers = status?.needs_review_workers_count ?? compliance?.needs_review_workers ?? 0;
  const activeIncidentsCount = status?.active_timers_count ?? violationSummary?.active_events_count ?? 0;
  const totalConfirmedViolations = violationSummary?.total_events_count ?? recentEvents.length;

  const complianceRate = activeWorkers > 0
    ? Math.round((compliantWorkers / activeWorkers) * 1000) / 10
    : 0.0;

  // Build evidence quick-lookup map
  const evidenceEventIds = useMemo(() => {
    const s = new Set<string>();
    for (const ev of evidenceRecords) {
      if (ev.event_id && (ev.image_filename || ev.evidence_image_filename)) {
        s.add(ev.event_id);
      }
    }
    return s;
  }, [evidenceRecords]);

  // Format recent violations rows with real evidence flags & timestamps
  const recentViolationRows: DemoViolation[] = useMemo(() => {
    const sevMap: Record<string, 'Critical' | 'High' | 'Medium'> = {
      critical: 'Critical',
      high: 'High',
      medium: 'Medium',
    };
    const statMap: Record<string, 'Open' | 'Ongoing' | 'Resolved'> = {
      open: 'Open',
      ongoing: 'Ongoing',
      resolved: 'Resolved',
      closed: 'Resolved',
    };

    return recentEvents.slice(0, 10).map((evt) => {
      const timeStr = evt.start_timestamp
        ? new Date(evt.start_timestamp * 1000).toLocaleTimeString([], {
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
          })
        : undefined;

      const cats = Array.isArray(evt.ppe_categories) && evt.ppe_categories.length > 0
        ? evt.ppe_categories
        : [evt.ppe_category || 'PPE Hazard'];

      return {
        eventId: evt.event_id,
        workerId: evt.worker_track_id,
        workerName: `Worker #${evt.worker_track_id}`,
        workerRole: 'Tracked Worker',
        ppeCategory: evt.ppe_category || cats[0],
        ppeCategories: cats,
        severity: sevMap[evt.severity?.toLowerCase()] || 'High',
        durationSeconds: Math.round(evt.violation_duration || 0),
        status: statMap[evt.status?.toLowerCase()] || 'Open',
        time: timeStr,
        hasEvidence: evidenceEventIds.has(evt.event_id),
      };
    });
  }, [recentEvents, evidenceEventIds]);

  // Format real compliance distribution slices
  const complianceDistribution: DemoDistributionSlice[] = useMemo(() => {
    return [
      { name: 'Compliant', value: compliantWorkers, tone: 'green' },
      { name: 'Needs review', value: reviewWorkers, tone: 'amber' },
      { name: 'Violation', value: nonCompliantWorkers, tone: 'red' },
    ];
  }, [compliantWorkers, reviewWorkers, nonCompliantWorkers]);

  // Format category counts from real backend summary, only including safety_shoes when model supports it!
  const categoryCounts: DemoCategoryCount[] = useMemo(() => {
    const rawCategories = violationSummary?.by_category || {};
    const baseCategories = ['hardhat', 'safety_vest', 'gloves', 'goggles', 'mask'];

    // Only include safety_shoes if supported by active model
    const supportsShoes = supportedPpe.some((p) => p.toLowerCase().includes('shoe') || p.toLowerCase().includes('boot'));
    const categoriesToEvaluate = supportsShoes ? [...baseCategories, 'safety_shoes'] : baseCategories;

    return categoriesToEvaluate.map((catKey) => {
      const displayName = catKey
        .split('_')
        .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
        .join(' ');
      return {
        category: displayName,
        count: rawCategories[catKey] || rawCategories[catKey.replace('_', ' ')] || 0,
      };
    });
  }, [violationSummary, supportedPpe]);

  return (
    <div className="space-y-6">
      {/* 1. System Overview Status Banner (Separating Backend vs Camera) */}
      <header className="glass-card rounded-2xl p-5 sm:p-6">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="space-y-1.5">
            <h2 className="text-2xl font-bold tracking-tight text-slate-900">System Overview</h2>
            <p className="max-w-2xl text-sm text-slate-600">
              Site-wide real-time snapshot of worker PPE compliance, safety violations, and active AI telemetry.
            </p>
            <p className="flex items-center gap-1.5 text-xs text-slate-500 font-medium">
              <CalendarClock className="h-3.5 w-3.5 text-slate-400" />
              Last telemetry sync: {lastUpdated.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={handleManualRefresh}
              disabled={isRefreshing}
              className="inline-flex items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 shadow-2xs transition hover:bg-slate-50 cursor-pointer"
            >
              <RefreshCw className={`h-3 w-3 ${isRefreshing ? 'animate-spin' : ''}`} />
              Refresh
            </button>
          </div>
        </div>

        {/* System Diagnostics Bar */}
        <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-5 border-t border-slate-200/80 pt-4 text-xs">
          {/* Backend Availability */}
          <div className="flex items-center gap-2 rounded-xl bg-slate-50/80 p-2.5">
            <Server className={`h-4 w-4 ${isBackendOnline ? 'text-emerald-600' : 'text-rose-600'}`} />
            <div>
              <p className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Backend API</p>
              <p className={`font-semibold ${isBackendOnline ? 'text-emerald-700' : 'text-rose-700'}`}>
                {isBackendOnline ? 'Online (FastAPI)' : 'Unavailable'}
              </p>
            </div>
          </div>

          {/* Camera Status */}
          <div className="flex items-center gap-2 rounded-xl bg-slate-50/80 p-2.5">
            <Camera className={`h-4 w-4 ${isRunning ? 'text-emerald-600' : 'text-slate-400'}`} />
            <div>
              <p className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Camera Device</p>
              <p className={`font-semibold ${isRunning ? 'text-emerald-700' : 'text-slate-600'}`}>
                {cameraState} {isRunning ? `(#${status?.camera_index ?? 0})` : ''}
              </p>
            </div>
          </div>

          {/* Monitoring State */}
          <div className="flex items-center gap-2 rounded-xl bg-slate-50/80 p-2.5">
            <div className={`h-2.5 w-2.5 rounded-full ${isRunning ? 'bg-emerald-500 animate-pulse' : 'bg-slate-400'}`} />
            <div>
              <p className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Monitoring State</p>
              <p className="font-semibold text-slate-800">
                {monitoringState} {isRunning ? `(${status?.current_fps?.toFixed(1) || 0} FPS)` : ''}
              </p>
            </div>
          </div>

          {/* Active AI Profile */}
          <div className="flex items-center gap-2 rounded-xl bg-slate-50/80 p-2.5">
            <Cpu className="h-4 w-4 text-blue-600" />
            <div className="min-w-0">
              <p className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Active AI Model</p>
              <p className="font-semibold text-slate-800 truncate" title={activeModelName}>
                {activeModelName}
              </p>
            </div>
          </div>

          {/* Monitoring Session */}
          <div className="flex items-center gap-2 rounded-xl bg-slate-50/80 p-2.5">
            <Layers className="h-4 w-4 text-indigo-600" />
            <div>
              <p className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Surveillance Session</p>
              <p className="font-semibold text-slate-800">
                {isRunning ? 'Session Active' : 'Session Standby'}
              </p>
            </div>
          </div>
        </div>
      </header>

      {/* 2. Seven Required KPI Cards */}
      <div className="grid grid-cols-1 gap-3.5 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-7">
        <KpiCard
          label="Active Workers"
          value={String(activeWorkers)}
          hint={isRunning ? 'In camera view' : 'Camera offline'}
          icon={Users}
          tone="blue"
        />
        <KpiCard
          label="Compliant Workers"
          value={String(compliantWorkers)}
          hint={`${compliantWorkers} of ${activeWorkers} compliant`}
          icon={UserCheck}
          tone="green"
        />
        <KpiCard
          label="Non-Compliant"
          value={String(nonCompliantWorkers)}
          hint={`${nonCompliantWorkers} violating PPE`}
          icon={UserX}
          tone={nonCompliantWorkers > 0 ? 'red' : 'green'}
        />
        <KpiCard
          label="Requires Review"
          value={String(reviewWorkers)}
          hint={`${reviewWorkers} unverified`}
          icon={AlertCircle}
          tone={reviewWorkers > 0 ? 'amber' : 'blue'}
        />
        <KpiCard
          label="Confirmed Violations"
          value={String(totalConfirmedViolations)}
          hint="Historical events"
          icon={ShieldAlert}
          tone={totalConfirmedViolations > 0 ? 'red' : 'green'}
        />
        <KpiCard
          label="Active Incidents"
          value={String(activeIncidentsCount)}
          hint={activeIncidentsCount > 0 ? 'Immediate action' : 'Zero active'}
          icon={TriangleAlert}
          tone={activeIncidentsCount > 0 ? 'red' : 'green'}
        />
        <KpiCard
          label="Compliance Rate"
          value={`${complianceRate}%`}
          hint={activeWorkers > 0 ? 'Current tracked' : 'No active workers'}
          icon={ShieldCheck}
          tone={complianceRate >= 80 ? 'green' : activeWorkers === 0 ? 'blue' : 'red'}
        />
      </div>

      {/* 3. Monitoring Summary + Real Charts */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <MonitoringSummary
          rows={[
            { label: 'Workers monitored', value: activeWorkers, tone: 'blue' },
            { label: 'Compliant workers', value: compliantWorkers, tone: 'green' },
            { label: 'Requiring review', value: reviewWorkers, tone: 'amber' },
            { label: 'Non-compliant workers', value: nonCompliantWorkers, tone: 'red' },
          ]}
        />
        <ComplianceDistributionChart data={complianceDistribution} />
        <ViolationCategoriesChart data={categoryCounts} />
      </div>

      {/* 4. Recent Confirmed Violations Table */}
      <div className="space-y-4">
        <RecentViolationsTable rows={recentViolationRows} />
      </div>
    </div>
  );
}
