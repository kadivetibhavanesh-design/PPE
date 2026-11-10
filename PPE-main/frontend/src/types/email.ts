export interface EmailSettings {
  enabled: boolean;
  recipient_email: string;
  sender_email?: string;
  smtp_host: string;
  smtp_port: number;
  smtp_username?: string;
  smtp_password?: string;
  has_password?: boolean;
  use_tls: boolean;
  use_ssl: boolean;
  reminder_interval_minutes: number;
}

export interface ActiveIncidentSchedule {
  incident_id: string;
  worker_track_id: number;
  ppe_category: string;
  status: string;
  first_alert_sent: boolean;
  reminder_count: number;
  next_reminder_timestamp: number | null;
}

export interface EmailStatus {
  enabled: boolean;
  smtp_configured: boolean;
  recipient_email: string;
  reminder_interval_minutes: number;
  total_emails_sent: number;
  failed_email_count: number;
  last_sent_timestamp: number | null;
  last_delivery_error: string | null;
  active_incident_schedules_count: number;
  active_incident_schedules: ActiveIncidentSchedule[];
}

export interface EmailHistoryRecord {
  id: string;
  timestamp: number;
  datetime: string;
  email_type: 'First Alert' | 'Reminder Alert' | 'Test Email' | string;
  incident_id: string;
  worker_id: number | null;
  violation_type: string;
  recipient: string;
  reminder_number: number;
  status: 'delivered' | 'failed';
  error: string | null;
}

export interface EmailHistoryResponse {
  total_records: number;
  history: EmailHistoryRecord[];
}

export interface TestEmailResult {
  success: boolean;
  message: string;
}

