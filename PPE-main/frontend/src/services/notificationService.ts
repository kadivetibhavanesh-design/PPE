import { apiClient } from './api';
import type {
  NotificationListResponse,
  UnreadCountResponse,
  NotificationCategory,
  NotificationSeverity,
} from '@/types/notification';

export interface GetNotificationsParams {
  limit?: number;
  offset?: number;
  unread_only?: boolean;
  category?: NotificationCategory;
  severity?: NotificationSeverity;
}

export const notificationService = {
  /**
   * Retrieves paginated system notifications with unread counts.
   */
  async getNotifications(params?: GetNotificationsParams): Promise<NotificationListResponse> {
    const res = await apiClient.get<NotificationListResponse>('/notifications', {
      params,
    });
    return res.data;
  },

  /**
   * Retrieves total unread notification count.
   */
  async getUnreadCount(): Promise<number> {
    const res = await apiClient.get<UnreadCountResponse>('/notifications/unread_count');
    return res.data.unread_count;
  },

  /**
   * Marks a single notification as read.
   */
  async markAsRead(notificationId: string): Promise<boolean> {
    const res = await apiClient.patch<{ success: boolean }>(
      `/notifications/${notificationId}/read`
    );
    return res.data.success;
  },

  /**
   * Marks all notifications as read.
   */
  async markAllAsRead(): Promise<number> {
    const res = await apiClient.post<{ success: boolean; marked_count: number }>(
      '/notifications/mark_all_read'
    );
    return res.data.marked_count;
  },

  /**
   * Clears all notifications history.
   */
  async clearAll(): Promise<number> {
    const res = await apiClient.delete<{ success: boolean; cleared_count: number }>(
      '/notifications'
    );
    return res.data.cleared_count;
  },

  /**
   * Deletes a single notification by ID.
   */
  async deleteNotification(notificationId: string): Promise<boolean> {
    const res = await apiClient.delete<{ success: boolean }>(
      `/notifications/${notificationId}`
    );
    return res.data.success;
  },
};

export default notificationService;
