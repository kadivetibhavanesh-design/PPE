import { useState, useEffect, useCallback, useMemo } from 'react';
import {
  FileText,
  ShieldCheck,
  ShieldAlert,
  Camera,
  RefreshCw,
  Download,
  CheckCircle2,
  Clock,
  Filter,
  Users,
  FileSpreadsheet,
  AlertCircle,
  ExternalLink,
} from 'lucide-react';
import PageHeader from '@/components/PageHeader';
import KpiCard from '@/components/KpiCard';
import SectionCard from '@/components/SectionCard';
import { reportService } from '@/services/reportService';
import type {
  ReportPeriod,
  ReportType,
  ReportsSummaryResponse,
  ReportsComplianceResponse,
  ReportsIncidentsResponse,
} from '@/types/reports';

export default function ReportsPage() {
  // Report selection & filter state
  const [reportType, setReportType] = useState<ReportType>('daily');
  const [period, setPeriod] = useState<ReportPeriod>('today');
  const [startDate, setStartDate] = useState<string>('');
  const [endDate, setEndDate] = useState<string>('');
  const [categoryFilter, setCategoryFilter] = useState<string>('all');
  const [statusFilter, setStatusFilter] = useState<string>('all');

  // Data states
  const [summary, setSummary] = useState<ReportsSummaryResponse | null>(null);
  const [complianceData, setComplianceData] = useState<ReportsComplianceResponse | null>(null);
  const [incidentsData, setIncidentsData] = useState<ReportsIncidentsResponse | null>(null);

  // UI state
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isExportingPdf, setIsExportingPdf] = useState<boolean>(false);
  const [isExportingCsv, setIsExportingCsv] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const fetchReportData = useCallback(async () => {
    setIsLoading(true);
    setErrorMessage(null);
    try {
      const filterParams = {
        period,
        start_date: period === 'custom' && startDate ? startDate : undefined,
        end_date: period === 'custom' && endDate ? endDate : undefined,
        category: categoryFilter !== 'all' ? categoryFilter : undefined,
        status: statusFilter !== 'all' ? statusFilter : undefined,
      };

      if (reportType === 'daily') {
        const [sumRes, incRes] = await Promise.all([
          reportService.getSummary(filterParams),
          reportService.getIncidents(filterParams),
        ]);
        setSummary(sumRes);
        setIncidentsData(incRes);
      } else if (reportType === 'compliance') {
        const compRes = await reportService.getCompliance(filterParams);
        setComplianceData(compRes);
        setSummary(compRes.summary);
      } else if (reportType === 'incidents') {
        const incRes = await reportService.getIncidents(filterParams);
        setIncidentsData(incRes);
        setSummary(incRes.summary);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to fetch report data from backend.';
      setErrorMessage(msg);
      console.error('[ReportsPage] Fetch error:', err);
    } finally {
      setIsLoading(false);
    }
  }, [reportType, period, startDate, endDate, categoryFilter, statusFilter]);

  useEffect(() => {
    fetchReportData();
  }, [fetchReportData]);

  // Export PDF handler
  const handleDownloadPdf = async () => {
    setIsExportingPdf(true);
    try {
      await reportService.downloadPdf({
        report_type: reportType,
        period,
        start_date: period === 'custom' && startDate ? startDate : undefined,
        end_date: period === 'custom' && endDate ? endDate : undefined,
        category: categoryFilter !== 'all' ? categoryFilter : undefined,
        status: statusFilter !== 'all' ? statusFilter : undefined,
      });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to generate PDF report.';
      alert(msg);
    } finally {
      setIsExportingPdf(false);
    }
  };

  // Export CSV handler
  const handleDownloadCsv = async () => {
    setIsExportingCsv(true);
    try {
      await reportService.downloadCsv({
        report_type: reportType,
        period,
        start_date: period === 'custom' && startDate ? startDate : undefined,
        end_date: period === 'custom' && endDate ? endDate : undefined,
        category: categoryFilter !== 'all' ? categoryFilter : undefined,
        status: statusFilter !== 'all' ? statusFilter : undefined,
      });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to generate CSV report.';
      alert(msg);
    } finally {
      setIsExportingCsv(false);
    }
  };

  // Metrics from summary
  const totalWorkers = summary?.total_workers_monitored || 0;
  const compliantWorkers = summary?.compliant_workers || 0;
  const nonCompliantWorkers = summary?.non_compliant_workers || 0;
  const overallCompliance = summary?.overall_compliance_percentage ?? 0;
  const totalViolations = summary?.total_violations || 0;
  const activeHazards = summary?.active_violations || 0;
  const resolvedCount = summary?.resolved_violations || 0;
  const uptimeStr = summary?.monitoring_uptime_formatted || '00h 00m 00s';

  const categoryDefinitions = useMemo(() => [
    { label: 'Hardhat', key: 'hardhat', severity: 'Critical', bg: 'bg-rose-500' },
    { label: 'Safety Vest', key: 'safety_vest', severity: 'High', bg: 'bg-amber-500' },
    { label: 'Safety Gloves', key: 'gloves', severity: 'Medium', bg: 'bg-blue-500' },
    { label: 'Eye Protection (Goggles)', key: 'goggles', severity: 'Medium', bg: 'bg-indigo-500' },
    { label: 'Protective Mask', key: 'mask', severity: 'Medium', bg: 'bg-purple-500' },
    { label: 'Safety Footwear', key: 'safety_shoes', severity: 'High', bg: 'bg-slate-500' },
  ], []);

  return (
    <div className="space-y-6">
      {/* 1. Header with Export Controls */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <PageHeader
          title="Safety Compliance Reports"
          description="Consolidated industrial safety audits, worker compliance distributions, and evidence logs."
        />
        <div className="flex flex-wrap items-center gap-2.5">
          <button
            type="button"
            onClick={fetchReportData}
            disabled={isLoading}
            className="inline-flex items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-3.5 py-2 text-xs font-semibold text-slate-700 shadow-xs transition hover:border-slate-300 hover:bg-slate-50 disabled:opacity-50"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${isLoading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
          <button
            type="button"
            onClick={handleDownloadCsv}
            disabled={isExportingCsv}
            className="inline-flex items-center gap-1.5 rounded-xl border border-emerald-300 bg-emerald-50 px-3.5 py-2 text-xs font-semibold text-emerald-800 shadow-xs transition hover:bg-emerald-100 disabled:opacity-50"
          >
            <FileSpreadsheet className={`h-3.5 w-3.5 ${isExportingCsv ? 'animate-pulse' : ''}`} />
            {isExportingCsv ? 'Exporting...' : 'Download CSV'}
          </button>
          <button
            type="button"
            onClick={handleDownloadPdf}
            disabled={isExportingPdf}
            className="inline-flex items-center gap-1.5 rounded-xl bg-brand-600 px-4 py-2 text-xs font-semibold text-white shadow-xs transition hover:bg-brand-700 disabled:opacity-50"
          >
            <Download className={`h-3.5 w-3.5 ${isExportingPdf ? 'animate-bounce' : ''}`} />
            {isExportingPdf ? 'Compiling PDF...' : 'Download PDF'}
          </button>
        </div>
      </div>

      {/* 2. Report Type Selector Tabs */}
      <div className="flex flex-wrap items-center gap-2 border-b border-slate-200 pb-2">
        <button
          type="button"
          onClick={() => setReportType('daily')}
          className={`inline-flex items-center gap-2 rounded-xl px-4 py-2 text-xs font-bold transition ${
            reportType === 'daily'
              ? 'bg-slate-900 text-white shadow-xs'
              : 'bg-white text-slate-600 hover:bg-slate-100 border border-slate-200'
          }`}
        >
          <FileText className="h-4 w-4" />
          A. Daily Safety Report
        </button>
        <button
          type="button"
          onClick={() => setReportType('compliance')}
          className={`inline-flex items-center gap-2 rounded-xl px-4 py-2 text-xs font-bold transition ${
            reportType === 'compliance'
              ? 'bg-slate-900 text-white shadow-xs'
              : 'bg-white text-slate-600 hover:bg-slate-100 border border-slate-200'
          }`}
        >
          <ShieldCheck className="h-4 w-4" />
          B. PPE Compliance Report
        </button>
        <button
          type="button"
          onClick={() => setReportType('incidents')}
          className={`inline-flex items-center gap-2 rounded-xl px-4 py-2 text-xs font-bold transition ${
            reportType === 'incidents'
              ? 'bg-slate-900 text-white shadow-xs'
              : 'bg-white text-slate-600 hover:bg-slate-100 border border-slate-200'
          }`}
        >
          <Camera className="h-4 w-4" />
          C. Incident & Evidence Report
        </button>
      </div>

      {/* 3. Filter Bar (Period, Date Range, Category, Status) */}
      <div className="rounded-2xl border border-slate-200/80 bg-white/80 p-4 shadow-xs backdrop-blur-md">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2 text-xs font-bold text-slate-700">
            <Filter className="h-4 w-4 text-brand-600" />
            <span>Report Filters:</span>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            {/* Period Selector */}
            <div className="flex items-center gap-1.5 text-xs">
              <span className="text-slate-500">Period:</span>
              <select
                value={period}
                onChange={(e) => setPeriod(e.target.value as ReportPeriod)}
                className="rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-xs font-semibold text-slate-700 shadow-xs focus:border-brand-500 focus:outline-none"
              >
                <option value="today">Today</option>
                <option value="yesterday">Yesterday</option>
                <option value="last_7_days">Last 7 Days</option>
                <option value="last_30_days">Last 30 Days</option>
                <option value="custom">Custom Date Range</option>
                <option value="all">All Records</option>
              </select>
            </div>

            {/* Custom Date Inputs if custom selected */}
            {period === 'custom' && (
              <div className="flex items-center gap-2">
                <input
                  type="date"
                  value={startDate}
                  onChange={(e) => setStartDate(e.target.value)}
                  className="rounded-lg border border-slate-200 bg-white px-2.5 py-1 text-xs text-slate-700 shadow-xs focus:border-brand-500"
                />
                <span className="text-xs text-slate-400">to</span>
                <input
                  type="date"
                  value={endDate}
                  onChange={(e) => setEndDate(e.target.value)}
                  className="rounded-lg border border-slate-200 bg-white px-2.5 py-1 text-xs text-slate-700 shadow-xs focus:border-brand-500"
                />
              </div>
            )}

            {/* Category Filter */}
            <div className="flex items-center gap-1.5 text-xs">
              <span className="text-slate-500">PPE Standard:</span>
              <select
                value={categoryFilter}
                onChange={(e) => setCategoryFilter(e.target.value)}
                className="rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-xs font-semibold text-slate-700 shadow-xs focus:border-brand-500 focus:outline-none"
              >
                <option value="all">All Standards</option>
                <option value="hardhat">Hardhat</option>
                <option value="safety_vest">Safety Vest</option>
                <option value="gloves">Gloves</option>
                <option value="goggles">Eye Protection</option>
                <option value="mask">Protective Mask</option>
                <option value="safety_shoes">Safety Footwear</option>
              </select>
            </div>

            {/* Status Filter */}
            <div className="flex items-center gap-1.5 text-xs">
              <span className="text-slate-500">Status:</span>
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-xs font-semibold text-slate-700 shadow-xs focus:border-brand-500 focus:outline-none"
              >
                <option value="all">All Statuses</option>
                <option value="open">Active / Ongoing</option>
                <option value="resolved">Resolved / Closed</option>
              </select>
            </div>
          </div>
        </div>
      </div>

      {/* Error Notice */}
      {errorMessage && (
        <div className="flex items-center gap-2.5 rounded-2xl border border-rose-200 bg-rose-50 p-4 text-xs font-medium text-rose-800">
          <AlertCircle className="h-4 w-4 shrink-0 text-rose-600" />
          <span>{errorMessage}</span>
        </div>
      )}

      {/* 4. Executive KPI Summary Cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <KpiCard
          label="Total Workers Monitored"
          value={totalWorkers.toString()}
          hint={totalWorkers > 0 ? `${compliantWorkers} compliant, ${nonCompliantWorkers} non-compliant` : 'Zero workers in view'}
          icon={Users}
          tone="blue"
        />
        <KpiCard
          label="Compliant Personnel"
          value={compliantWorkers.toString()}
          hint={`${overallCompliance}% compliance rate`}
          icon={ShieldCheck}
          tone="green"
        />
        <KpiCard
          label="Total Safety Violations"
          value={totalViolations.toString()}
          hint={`${activeHazards} active, ${resolvedCount} resolved`}
          icon={ShieldAlert}
          tone={totalViolations > 0 ? 'red' : 'green'}
        />
        <KpiCard
          label="Surveillance Duration"
          value={uptimeStr}
          hint={summary?.is_monitoring_active ? 'Camera active now' : 'Camera currently idle'}
          icon={Clock}
          tone="amber"
        />
      </div>

      {/* 5. Report Type Specific Content */}

      {/* REPORT TYPE A: DAILY SAFETY REPORT */}
      {reportType === 'daily' && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            {/* Severity Distribution */}
            <SectionCard
              title="Incident Breakdown by Severity"
              subtitle="Distribution across safety hazard risk levels"
            >
              {totalViolations === 0 ? (
                <div className="flex h-44 flex-col items-center justify-center text-center text-slate-400">
                  <CheckCircle2 className="h-8 w-8 text-emerald-500" />
                  <p className="mt-2 text-sm font-semibold text-slate-700">Zero Violations Logged</p>
                  <p className="mt-0.5 text-xs text-slate-500">Every safety regulation satisfied for this time period.</p>
                </div>
              ) : (
                <div className="space-y-4 py-2">
                  <div>
                    <div className="flex justify-between text-xs font-semibold text-slate-700">
                      <span className="flex items-center gap-2">
                        <span className="h-2.5 w-2.5 rounded-full bg-rose-500" />
                        Critical Severity (Hardhat)
                      </span>
                      <span>{summary?.critical_violations || 0} ({totalViolations > 0 ? Math.round(((summary?.critical_violations || 0) / totalViolations) * 100) : 0}%)</span>
                    </div>
                    <div className="mt-1.5 h-2 w-full overflow-hidden rounded-full bg-slate-100">
                      <div
                        className="h-full rounded-full bg-rose-500"
                        style={{ width: `${totalViolations > 0 ? ((summary?.critical_violations || 0) / totalViolations) * 100 : 0}%` }}
                      />
                    </div>
                  </div>

                  <div>
                    <div className="flex justify-between text-xs font-semibold text-slate-700">
                      <span className="flex items-center gap-2">
                        <span className="h-2.5 w-2.5 rounded-full bg-amber-500" />
                        High Severity (Safety Vest, Shoes)
                      </span>
                      <span>{summary?.high_violations || 0} ({totalViolations > 0 ? Math.round(((summary?.high_violations || 0) / totalViolations) * 100) : 0}%)</span>
                    </div>
                    <div className="mt-1.5 h-2 w-full overflow-hidden rounded-full bg-slate-100">
                      <div
                        className="h-full rounded-full bg-amber-500"
                        style={{ width: `${totalViolations > 0 ? ((summary?.high_violations || 0) / totalViolations) * 100 : 0}%` }}
                      />
                    </div>
                  </div>

                  <div>
                    <div className="flex justify-between text-xs font-semibold text-slate-700">
                      <span className="flex items-center gap-2">
                        <span className="h-2.5 w-2.5 rounded-full bg-blue-500" />
                        Medium Severity (Gloves, Mask, Goggles)
                      </span>
                      <span>{summary?.medium_violations || 0} ({totalViolations > 0 ? Math.round(((summary?.medium_violations || 0) / totalViolations) * 100) : 0}%)</span>
                    </div>
                    <div className="mt-1.5 h-2 w-full overflow-hidden rounded-full bg-slate-100">
                      <div
                        className="h-full rounded-full bg-blue-500"
                        style={{ width: `${totalViolations > 0 ? ((summary?.medium_violations || 0) / totalViolations) * 100 : 0}%` }}
                      />
                    </div>
                  </div>
                </div>
              )}
            </SectionCard>

            {/* Category Breakdown */}
            <SectionCard
              title="Violations by PPE Category"
              subtitle="Counts per mandatory industrial personal protective equipment"
            >
              <div className="grid grid-cols-2 gap-3 py-1">
                {categoryDefinitions.map((c) => {
                  const count = summary?.violation_category_breakdown?.[c.key] || 0;
                  return (
                    <div
                      key={c.key}
                      className="flex flex-col rounded-xl border border-slate-200/80 bg-slate-50/50 p-3"
                    >
                      <span className="text-xs font-medium text-slate-600">{c.label}</span>
                      <div className="mt-1 flex items-baseline justify-between">
                        <span className="text-lg font-bold text-slate-900">{count}</span>
                        <span className="text-xs text-slate-400">
                          {totalViolations > 0 ? `${Math.round((count / totalViolations) * 100)}%` : '0%'}
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </SectionCard>
          </div>

          {/* Incidents Table in Daily Report */}
          <SectionCard
            title="Recorded Safety Incidents & Evidence"
            subtitle="Verified continuous violations and captured local camera frames"
          >
            {(!incidentsData || incidentsData.incidents.length === 0) ? (
              <div className="flex flex-col items-center justify-center py-10 text-center text-slate-400">
                <CheckCircle2 className="h-8 w-8 text-emerald-500" />
                <p className="mt-2 text-sm font-semibold text-slate-700">No Incidents Found</p>
                <p className="mt-0.5 text-xs text-slate-500">Zero safety violations detected during this period.</p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-slate-200 text-left text-sm">
                  <thead className="bg-slate-50/75 text-xs font-semibold uppercase tracking-wider text-slate-500">
                    <tr>
                      <th scope="col" className="px-4 py-3">Event ID</th>
                      <th scope="col" className="px-4 py-3">Worker</th>
                      <th scope="col" className="px-4 py-3">Violation Type</th>
                      <th scope="col" className="px-4 py-3">Severity</th>
                      <th scope="col" className="px-4 py-3">Timestamp</th>
                      <th scope="col" className="px-4 py-3">Status</th>
                      <th scope="col" className="px-4 py-3 text-right">Photo Evidence</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 bg-white/60">
                    {incidentsData.incidents.slice(0, 10).map((inc) => (
                      <tr key={inc.incident_id} className="hover:bg-slate-50/80">
                        <td className="whitespace-nowrap px-4 py-3 font-mono text-xs font-bold text-slate-900">
                          {inc.incident_id}
                        </td>
                        <td className="whitespace-nowrap px-4 py-3 text-xs text-slate-700 font-semibold">
                          Worker #{inc.worker_id}
                        </td>
                        <td className="whitespace-nowrap px-4 py-3 text-xs font-medium text-slate-800">
                          {inc.violation_type}
                        </td>
                        <td className="whitespace-nowrap px-4 py-3">
                          <span
                            className={`inline-flex items-center rounded-md px-2 py-0.5 text-xs font-semibold capitalize ${
                              inc.severity.toLowerCase() === 'critical'
                                ? 'bg-rose-100 text-rose-800'
                                : inc.severity.toLowerCase() === 'high'
                                ? 'bg-amber-100 text-amber-800'
                                : 'bg-blue-100 text-blue-800'
                            }`}
                          >
                            {inc.severity}
                          </span>
                        </td>
                        <td className="whitespace-nowrap px-4 py-3 text-xs text-slate-600">
                          {inc.datetime}
                        </td>
                        <td className="whitespace-nowrap px-4 py-3">
                          <span
                            className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
                              inc.status.toLowerCase() === 'resolved' || inc.status.toLowerCase() === 'closed'
                                ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                                : 'bg-rose-50 text-rose-700 border border-rose-200'
                            }`}
                          >
                            {inc.status}
                          </span>
                        </td>
                        <td className="whitespace-nowrap px-4 py-3 text-right">
                          {inc.evidence_image_available ? (
                            <a
                              href={reportService.getEvidenceImageUrl(inc.incident_id)}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="inline-flex items-center gap-1 text-xs font-semibold text-brand-600 hover:text-brand-800"
                            >
                              <Camera className="h-3.5 w-3.5" />
                              View Image
                              <ExternalLink className="h-3 w-3" />
                            </a>
                          ) : (
                            <span className="text-xs text-slate-400">None</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </SectionCard>
        </div>
      )}

      {/* REPORT TYPE B: PPE COMPLIANCE REPORT */}
      {reportType === 'compliance' && (
        <div className="space-y-6">
          {/* Category Standards Table */}
          <SectionCard
            title="PPE Category Standards Compliance"
            subtitle="Live safety compliance rates evaluated across 6 mandatory protective equipment categories"
          >
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-slate-200 text-left text-sm">
                <thead className="bg-slate-50/75 text-xs font-semibold uppercase tracking-wider text-slate-500">
                  <tr>
                    <th scope="col" className="px-4 py-3">PPE Equipment Standard</th>
                    <th scope="col" className="px-4 py-3 text-center">Total Monitored</th>
                    <th scope="col" className="px-4 py-3 text-center">Compliant Personnel</th>
                    <th scope="col" className="px-4 py-3 text-center">Violations Logged</th>
                    <th scope="col" className="px-4 py-3 text-right">Compliance Percentage</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 bg-white/60">
                  {complianceData?.category_compliance.map((cat) => (
                    <tr key={cat.key} className="hover:bg-slate-50/80">
                      <td className="whitespace-nowrap px-4 py-3 text-xs font-bold text-slate-900">
                        {cat.category}
                      </td>
                      <td className="whitespace-nowrap px-4 py-3 text-center text-xs text-slate-600">
                        {cat.total_monitored}
                      </td>
                      <td className="whitespace-nowrap px-4 py-3 text-center text-xs text-emerald-700 font-semibold">
                        {cat.compliant_count}
                      </td>
                      <td className="whitespace-nowrap px-4 py-3 text-center text-xs text-rose-700 font-semibold">
                        {cat.violation_count}
                      </td>
                      <td className="whitespace-nowrap px-4 py-3 text-right">
                        <span
                          className={`inline-flex items-center rounded-lg px-2.5 py-0.5 text-xs font-bold ${
                            cat.compliance_rate >= 90
                              ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                              : cat.compliance_rate >= 75
                              ? 'bg-amber-50 text-amber-700 border border-amber-200'
                              : 'bg-rose-50 text-rose-700 border border-rose-200'
                          }`}
                        >
                          {cat.compliance_rate}%
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </SectionCard>

          {/* Worker Compliance Matrix */}
          <SectionCard
            title="Worker-Wise PPE Compliance Matrix"
            subtitle="Personnel-specific safety gear evaluation and violation history"
          >
            {(!complianceData?.worker_compliance || complianceData.worker_compliance.length === 0) ? (
              <div className="flex flex-col items-center justify-center py-10 text-center text-slate-400">
                <Users className="h-8 w-8 text-slate-300" />
                <p className="mt-2 text-sm font-semibold text-slate-700">No Workers Tracked</p>
                <p className="mt-0.5 text-xs text-slate-500">
                  Start live monitoring to evaluate worker personnel in real time.
                </p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-slate-200 text-left text-sm">
                  <thead className="bg-slate-50/75 text-xs font-semibold uppercase tracking-wider text-slate-500">
                    <tr>
                      <th scope="col" className="px-4 py-3">Worker ID</th>
                      <th scope="col" className="px-4 py-3">Surveillance Status</th>
                      <th scope="col" className="px-4 py-3">Compliance State</th>
                      <th scope="col" className="px-4 py-3 text-center">Violations Logged</th>
                      <th scope="col" className="px-4 py-3">Missing PPE Gear</th>
                      <th scope="col" className="px-4 py-3 text-right">Last Seen</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 bg-white/60">
                    {complianceData.worker_compliance.map((w) => (
                      <tr key={w.worker_id} className="hover:bg-slate-50/80">
                        <td className="whitespace-nowrap px-4 py-3 font-mono text-xs font-bold text-slate-900">
                          Worker #{w.worker_id}
                        </td>
                        <td className="whitespace-nowrap px-4 py-3 text-xs text-slate-600">
                          {w.status}
                        </td>
                        <td className="whitespace-nowrap px-4 py-3">
                          <span
                            className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold ${
                              w.compliance_status.toLowerCase().includes('compliant') && !w.compliance_status.toLowerCase().includes('non')
                                ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                                : w.compliance_status.toLowerCase().includes('review')
                                ? 'bg-amber-50 text-amber-700 border border-amber-200'
                                : 'bg-rose-50 text-rose-700 border border-rose-200'
                            }`}
                          >
                            {w.compliance_status}
                          </span>
                        </td>
                        <td className="whitespace-nowrap px-4 py-3 text-center font-bold text-xs text-slate-900">
                          {w.violations_count}
                        </td>
                        <td className="whitespace-nowrap px-4 py-3 text-xs text-slate-700">
                          {w.missing_categories.length > 0 ? (
                            <span className="text-rose-600 font-medium">
                              {w.missing_categories.join(', ')}
                            </span>
                          ) : (
                            <span className="text-emerald-600 font-medium">All Equipment Verified</span>
                          )}
                        </td>
                        <td className="whitespace-nowrap px-4 py-3 text-right text-xs text-slate-500">
                          {w.last_seen}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {/* Historical Note */}
            <div className="mt-4 rounded-xl border border-slate-200 bg-slate-50 p-3 text-xs text-slate-500">
              <span className="font-semibold text-slate-700">Data Source Note: </span>
              {complianceData?.historical_limitation_note}
            </div>
          </SectionCard>
        </div>
      )}

      {/* REPORT TYPE C: INCIDENT REPORT */}
      {reportType === 'incidents' && (
        <SectionCard
          title="Industrial Incident & Evidence Log"
          subtitle="Complete audit trail of confirmed PPE violations with captured JPEG evidence photos"
        >
          {(!incidentsData || incidentsData.incidents.length === 0) ? (
            <div className="flex flex-col items-center justify-center py-12 text-center text-slate-400">
              <Camera className="h-8 w-8 text-slate-300" />
              <p className="mt-2 text-sm font-semibold text-slate-700">No Incidents Recorded</p>
              <p className="mt-0.5 text-xs text-slate-500">No safety violations match the selected time range or filter criteria.</p>
            </div>
          ) : (
            <div className="space-y-4">
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-slate-200 text-left text-sm">
                  <thead className="bg-slate-50/75 text-xs font-semibold uppercase tracking-wider text-slate-500">
                    <tr>
                      <th scope="col" className="px-4 py-3">Incident ID</th>
                      <th scope="col" className="px-4 py-3">Worker</th>
                      <th scope="col" className="px-4 py-3">Violation Type</th>
                      <th scope="col" className="px-4 py-3">Severity</th>
                      <th scope="col" className="px-4 py-3">Detected Time</th>
                      <th scope="col" className="px-4 py-3">Status</th>
                      <th scope="col" className="px-4 py-3">Duration</th>
                      <th scope="col" className="px-4 py-3 text-right">Photo Evidence</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 bg-white/60">
                    {incidentsData.incidents.map((inc) => (
                      <tr key={inc.incident_id} className="hover:bg-slate-50/80">
                        <td className="whitespace-nowrap px-4 py-3 font-mono text-xs font-bold text-slate-900">
                          {inc.incident_id}
                        </td>
                        <td className="whitespace-nowrap px-4 py-3 text-xs font-semibold text-slate-700">
                          Worker #{inc.worker_id}
                        </td>
                        <td className="whitespace-nowrap px-4 py-3 text-xs font-medium text-slate-800">
                          {inc.violation_type}
                        </td>
                        <td className="whitespace-nowrap px-4 py-3">
                          <span
                            className={`inline-flex items-center rounded-md px-2 py-0.5 text-xs font-semibold capitalize ${
                              inc.severity.toLowerCase() === 'critical'
                                ? 'bg-rose-100 text-rose-800'
                                : inc.severity.toLowerCase() === 'high'
                                ? 'bg-amber-100 text-amber-800'
                                : 'bg-blue-100 text-blue-800'
                            }`}
                          >
                            {inc.severity}
                          </span>
                        </td>
                        <td className="whitespace-nowrap px-4 py-3 text-xs text-slate-600">
                          {inc.datetime}
                        </td>
                        <td className="whitespace-nowrap px-4 py-3">
                          <span
                            className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold ${
                              inc.status.toLowerCase() === 'resolved' || inc.status.toLowerCase() === 'closed'
                                ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                                : 'bg-rose-50 text-rose-700 border border-rose-200'
                            }`}
                          >
                            {inc.status}
                          </span>
                        </td>
                        <td className="whitespace-nowrap px-4 py-3 text-xs text-slate-600">
                          {inc.duration_seconds}s
                        </td>
                        <td className="whitespace-nowrap px-4 py-3 text-right">
                          {inc.evidence_image_available ? (
                            <a
                              href={reportService.getEvidenceImageUrl(inc.incident_id)}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="inline-flex items-center gap-1.5 rounded-lg border border-brand-200 bg-brand-50 px-2.5 py-1 text-xs font-semibold text-brand-700 hover:bg-brand-100 transition"
                            >
                              <Camera className="h-3.5 w-3.5" />
                              Inspect Photo
                              <ExternalLink className="h-3 w-3" />
                            </a>
                          ) : (
                            <span className="text-xs text-slate-400">No Image</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </SectionCard>
      )}
    </div>
  );
}
