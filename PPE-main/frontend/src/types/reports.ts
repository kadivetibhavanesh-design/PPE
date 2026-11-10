export type ReportPeriod = 'today' | 'yesterday' | 'last_7_days' | 'last_30_days' | 'custom' | 'all';
export type ReportType = 'daily' | 'compliance' | 'incidents';

export interface ReportsSummaryResponse {
  period: string;
  start_time: string;
  end_time: string;
  generated_at: string;
  monitoring_duration_seconds: number;
  monitoring_uptime_formatted: string;
  is_monitoring_active: boolean;
  active_model_id: string;
  active_model_name: string;
  total_workers_monitored: number;
  compliant_workers: number;
  non_compliant_workers: number;
  review_workers: number;
  overall_compliance_percentage: number;
  total_violations: number;
  active_violations: number;
  resolved_violations: number;
  critical_violations: number;
  high_violations: number;
  medium_violations: number;
  violation_category_breakdown: Record<string, number>;
  incident_summary: {
    total_incidents: number;
    with_evidence_image: number;
    resolved_count: number;
    active_count: number;
    resolution_rate_percentage: number;
  };
}

export interface CategoryComplianceItem {
  category: string;
  key: string;
  total_monitored: number;
  compliant_count: number;
  violation_count: number;
  compliance_rate: number;
}

export interface WorkerComplianceItem {
  worker_id: number;
  status: string;
  compliance_status: string;
  missing_categories: string[];
  violations_count: number;
  last_seen: string;
}

export interface ViolationFrequencyItem {
  category: string;
  key: string;
  count: number;
  percentage: number;
}

export interface ReportsComplianceResponse {
  summary: ReportsSummaryResponse;
  overall_compliance_percentage: number;
  category_compliance: CategoryComplianceItem[];
  worker_compliance: WorkerComplianceItem[];
  violation_frequency: ViolationFrequencyItem[];
  historical_limitation_note: string;
}

export interface IncidentReportItem {
  incident_id: string;
  timestamp: number;
  datetime: string;
  worker_id: number;
  violation_type: string;
  category_key: string;
  severity: string;
  status: string;
  duration_seconds: number;
  evidence_image_available: boolean;
  evidence_image_url?: string | null;
  resolution_datetime?: string | null;
}

export interface ReportsIncidentsResponse {
  summary: ReportsSummaryResponse;
  total_count: number;
  incidents: IncidentReportItem[];
}

export interface ReportFilterParams {
  period?: ReportPeriod;
  start_date?: string;
  end_date?: string;
  category?: string;
  status?: string;
  report_type?: ReportType;
}

