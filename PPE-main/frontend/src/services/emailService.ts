import apiClient from '@/services/api';
import type {
  EmailSettings,
  EmailStatus,
  EmailHistoryResponse,
  EmailHistoryRecord,
  TestEmailResult,
} from '@/types/email';

export const emailService = {
  /**
   * Retrieves email configuration settings (passwords masked as '******').
   */
  async getEmailSettings(): Promise<EmailSettings> {
    const res = await apiClient.get<EmailSettings>('/api/settings/email');
    return res.data;
  },

  /**
   * Updates email notification configuration (recipient, SMTP, reminder interval).
   */
  async updateEmailSettings(updates: Partial<EmailSettings>): Promise<{ success: boolean; settings: EmailSettings; email?: EmailSettings }> {
    const res = await apiClient.put<{ success: boolean; settings?: EmailSettings; email?: EmailSettings }>('/api/settings/email', updates);
    const data = res.data;
    const settings = (data.settings || data.email || {}) as EmailSettings;
    return {
      success: Boolean(data.success),
      settings,
      email: settings,
    };
  },

  /**
   * Dispatches an independent test email to verify SMTP and recipient reachability.
   */
  async sendTestEmail(recipientEmail?: string): Promise<TestEmailResult> {
    const res = await apiClient.post<TestEmailResult>('/api/settings/email/test', {
      recipient_email: recipientEmail,
    });
    return res.data;
  },

  /**
   * Retrieves real-time email notification status, counters, and active schedules.
   */
  async getEmailStatus(): Promise<EmailStatus> {
    const res = await apiClient.get<EmailStatus>('/api/notifications/email/status');
    return res.data;
  },

  /**
   * Retrieves email delivery history logs (most recent first).
   */
  async getEmailHistory(limit: number = 50): Promise<EmailHistoryResponse> {
    const res = await apiClient.get<EmailHistoryResponse>('/api/notifications/email/history', {
      params: { limit },
    });
    return res.data;
  },

  /**
   * Retrieves delivery history for a specific incident.
   */
  async getIncidentEmailHistory(incidentId: string): Promise<EmailHistoryRecord[]> {
    const res = await apiClient.get<EmailHistoryRecord[]>(`/api/notifications/email/incident/${incidentId}`);
    return res.data;
  },
};

export default emailService;

