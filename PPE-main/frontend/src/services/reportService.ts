import { apiClient, API_BASE_URL } from '@/services/api';
import type {
  ReportFilterParams,
  ReportsSummaryResponse,
  ReportsComplianceResponse,
  ReportsIncidentsResponse,
} from '@/types/reports';

export const reportService = {
  /**
   * Fetches the executive summary metrics for reports.
   * Endpoint: GET /api/reports/summary
   */
  async getSummary(params?: ReportFilterParams): Promise<ReportsSummaryResponse> {
    const response = await apiClient.get<ReportsSummaryResponse>('/api/reports/summary', {
      params,
    });
    return response.data;
  },

  /**
   * Fetches detailed PPE and worker compliance analysis.
   * Endpoint: GET /api/reports/compliance
   */
  async getCompliance(params?: ReportFilterParams): Promise<ReportsComplianceResponse> {
    const response = await apiClient.get<ReportsComplianceResponse>('/api/reports/compliance', {
      params,
    });
    return response.data;
  },

  /**
   * Fetches detailed incident logs.
   * Endpoint: GET /api/reports/incidents
   */
  async getIncidents(params?: ReportFilterParams): Promise<ReportsIncidentsResponse> {
    const response = await apiClient.get<ReportsIncidentsResponse>('/api/reports/incidents', {
      params,
    });
    return response.data;
  },

  /**
   * Downloads a generated PDF report with embedded evidence images.
   * Endpoint: GET /api/reports/export/pdf
   */
  async downloadPdf(params?: ReportFilterParams): Promise<void> {
    const response = await apiClient.get('/api/reports/export/pdf', {
      params,
      responseType: 'blob',
    });

    const blob = new Blob([response.data], { type: 'application/pdf' });
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    const rType = params?.report_type || 'daily';
    const period = params?.period || 'today';
    link.setAttribute('download', `SafeVision_${rType}_report_${period}.pdf`);
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url);
  },

  /**
   * Downloads a generated CSV report.
   * Endpoint: GET /api/reports/export/csv
   */
  async downloadCsv(params?: ReportFilterParams): Promise<void> {
    const response = await apiClient.get('/api/reports/export/csv', {
      params,
      responseType: 'blob',
    });

    const blob = new Blob([response.data], { type: 'text/csv;charset=utf-8;' });
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    const rType = params?.report_type || 'daily';
    const period = params?.period || 'today';
    link.setAttribute('download', `SafeVision_${rType}_report_${period}.csv`);
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url);
  },

  /**
   * Returns full URL for viewing an incident evidence photo.
   */
  getEvidenceImageUrl(eventId: string): string {
    return `${API_BASE_URL}/api/evidence/${encodeURIComponent(eventId)}/image`;
  },
};

export default reportService;

