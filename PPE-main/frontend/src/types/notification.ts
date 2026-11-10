export type NotificationCategory = 'ppe' | 'alarm' | 'email' | 'monitoring';
export type NotificationSeverity = 'critical' | 'high' | 'medium' | 'low' | 'info';

export interface AppNotification {
  id: string;
  event_type: string;
  category: NotificationCategory;
  title: string;
  description: string;
  severity: NotificationSeverity;
  timestamp: number;
  datetime?: string;
  read: boolean;
  worker_id?: number | null;
  incident_id?: string | null;
  destination?: string | null;
  metadata?: Record<string, unknown>;
}

export interface NotificationListResponse {
  total: number;
  unread_count: number;
  notifications: AppNotification[];
}

export interface UnreadCountResponse {
  unread_count: number;
}

