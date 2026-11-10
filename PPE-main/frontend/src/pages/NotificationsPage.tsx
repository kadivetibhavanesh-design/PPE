import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { CircularProgress } from '@mui/material';
import {
  Bell,
  CheckCheck,
  Trash2,
  HardHat,
  BellRing,
  Mail,
  Camera,
  ExternalLink,
  ShieldAlert,
  AlertTriangle,
  Info,
  CheckCircle2,
  RefreshCw,
  Filter,
} from 'lucide-react';
import SectionCard from '@/components/SectionCard';
import { notificationService } from '@/services/notificationService';
import { websocketService } from '@/services/websocketService';
import type {
  AppNotification,
  NotificationCategory,
  NotificationSeverity,
} from '@/types/notification';
import type { WebSocketMessage } from '@/types/monitoring';

export const NotificationsPage: React.FC = () => {
  const navigate = useNavigate();
  const [notifications, setNotifications] = useState<AppNotification[]>([]);
  const [unreadCount, setUnreadCount] = useState<number>(0);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [selectedCategory, setSelectedCategory] = useState<string>('all');
  const [selectedSeverity, setSelectedSeverity] = useState<string>('all');
  const [readFilter, setReadFilter] = useState<'all' | 'unread' | 'read'>('all');

  const [isClearing, setIsClearing] = useState<boolean>(false);
  const [isMarkingAll, setIsMarkingAll] = useState<boolean>(false);

  const fetchNotifications = useCallback(async (quiet = false) => {
    if (!quiet) setIsLoading(true);
    setError(null);
    try {
      const data = await notificationService.getNotifications({ limit: 150 });
      setNotifications(data.notifications);
      setUnreadCount(data.unread_count);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to retrieve notifications';
      setError(msg);
    } finally {
      if (!quiet) setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchNotifications();
  }, [fetchNotifications]);

  // Real-time WebSocket listener
  useEffect(() => {
    const handleWsMessage = (msg: WebSocketMessage) => {
      if (msg.type === 'notification' && msg.data) {
        const newNotif = msg.data;
        setNotifications((prev) => {
          if (prev.some((n) => n.id === newNotif.id)) return prev;
          return [newNotif, ...prev];
        });
        setUnreadCount((c) => c + 1);
      }
    };

    const unsubscribe = websocketService.onMessage(handleWsMessage);
    return () => unsubscribe();
  }, []);

  const handleMarkAsRead = async (notifId: string) => {
    try {
      await notificationService.markAsRead(notifId);
      setNotifications((prev) =>
        prev.map((n) => (n.id === notifId ? { ...n, read: true } : n))
      );
      setUnreadCount((c) => Math.max(0, c - 1));
    } catch (err) {
      console.error('Failed to mark notification as read:', err);
    }
  };

  const handleMarkAllAsRead = async () => {
    if (unreadCount === 0 || isMarkingAll) return;
    setIsMarkingAll(true);
    try {
      await notificationService.markAllAsRead();
      setNotifications((prev) => prev.map((n) => ({ ...n, read: true })));
      setUnreadCount(0);
    } catch (err) {
      console.error('Failed to mark all as read:', err);
    } finally {
      setIsMarkingAll(false);
    }
  };

  const handleClearAll = async () => {
    if (notifications.length === 0 || isClearing) return;
    if (!window.confirm('Are you sure you want to clear all notification history?')) return;
    setIsClearing(true);
    try {
      await notificationService.clearAll();
      setNotifications([]);
      setUnreadCount(0);
    } catch (err) {
      console.error('Failed to clear notifications:', err);
    } finally {
      setIsClearing(false);
    }
  };

  // Filter application
  const filteredNotifications = notifications.filter((notif) => {
    if (selectedCategory !== 'all' && notif.category !== selectedCategory) return false;
    if (selectedSeverity !== 'all' && notif.severity !== selectedSeverity) return false;
    if (readFilter === 'unread' && notif.read) return false;
    if (readFilter === 'read' && !notif.read) return false;
    return true;
  });

  const getCategoryIcon = (category: NotificationCategory) => {
    switch (category) {
      case 'ppe':
        return <HardHat className="h-4 w-4 text-rose-600" />;
      case 'alarm':
        return <BellRing className="h-4 w-4 text-amber-600" />;
      case 'email':
        return <Mail className="h-4 w-4 text-blue-600" />;
      case 'monitoring':
        return <Camera className="h-4 w-4 text-emerald-600" />;
      default:
        return <Info className="h-4 w-4 text-slate-500" />;
    }
  };

  const getSeverityBadge = (severity: NotificationSeverity) => {
    switch (severity) {
      case 'critical':
        return (
          <span className="inline-flex items-center gap-1 rounded px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider bg-rose-100 text-rose-800 border border-rose-200">
            <ShieldAlert className="h-2.5 w-2.5" />
            Critical
          </span>
        );
      case 'high':
        return (
          <span className="inline-flex items-center gap-1 rounded px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider bg-orange-100 text-orange-800 border border-orange-200">
            <AlertTriangle className="h-2.5 w-2.5" />
            High
          </span>
        );
      case 'medium':
        return (
          <span className="inline-flex items-center gap-1 rounded px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider bg-amber-100 text-amber-800 border border-amber-200">
            <AlertTriangle className="h-2.5 w-2.5" />
            Medium
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 rounded px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider bg-blue-100 text-blue-800 border border-blue-200">
            <Info className="h-2.5 w-2.5" />
            Info
          </span>
        );
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <header className="glass-card rounded-2xl p-5 sm:p-6">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="space-y-1.5">
            <div className="flex items-center gap-3">
              <h2 className="text-2xl font-bold tracking-tight text-slate-900">Notification Center</h2>
              {unreadCount > 0 && (
                <span className="inline-flex items-center gap-1.5 rounded-full bg-blue-100 px-3 py-0.5 text-xs font-bold text-blue-800">
                  <Bell className="h-3 w-3 text-blue-600" />
                  {unreadCount} Unread
                </span>
              )}
            </div>
            <p className="max-w-2xl text-sm text-slate-600">
              Chronological audit log of confirmed PPE violations, hardware alarms, automated email alerts, and camera monitoring lifecycle events.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {unreadCount > 0 && (
              <button
                type="button"
                onClick={handleMarkAllAsRead}
                disabled={isMarkingAll}
                className="inline-flex items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-3.5 py-2 text-xs font-semibold text-slate-700 shadow-2xs hover:bg-slate-50 transition cursor-pointer"
              >
                {isMarkingAll ? (
                  <CircularProgress size={14} color="inherit" />
                ) : (
                  <CheckCheck className="h-3.5 w-3.5 text-blue-600" />
                )}
                Mark all read
              </button>
            )}

            {notifications.length > 0 && (
              <button
                type="button"
                onClick={handleClearAll}
                disabled={isClearing}
                className="inline-flex items-center gap-1.5 rounded-xl border border-rose-200 bg-rose-50 px-3.5 py-2 text-xs font-semibold text-rose-700 shadow-2xs hover:bg-rose-100 transition cursor-pointer"
              >
                {isClearing ? (
                  <CircularProgress size={14} color="inherit" />
                ) : (
                  <Trash2 className="h-3.5 w-3.5" />
                )}
                Clear history
              </button>
            )}

            <button
              type="button"
              onClick={() => fetchNotifications(false)}
              disabled={isLoading}
              className="inline-flex items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-3.5 py-2 text-xs font-semibold text-slate-700 shadow-2xs hover:bg-slate-50 transition cursor-pointer"
            >
              <RefreshCw className={`h-3.5 w-3.5 ${isLoading ? 'animate-spin' : ''}`} />
              Refresh
            </button>
          </div>
        </div>
      </header>

      {/* Filter Toolbar */}
      <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-2xs">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex flex-wrap items-center gap-3">
            <div className="flex items-center gap-1 text-xs font-bold text-slate-500 uppercase tracking-wide">
              <Filter className="h-3.5 w-3.5" />
              Filter by:
            </div>

            {/* Category Filter */}
            <select
              value={selectedCategory}
              onChange={(e) => setSelectedCategory(e.target.value)}
              className="rounded-xl border border-slate-300 bg-slate-50 px-3 py-1.5 text-xs font-semibold text-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
            >
              <option value="all">All Categories</option>
              <option value="ppe">PPE Violations</option>
              <option value="alarm">Audio/Visual Alarms</option>
              <option value="email">Email Alert Delivery</option>
              <option value="monitoring">Camera Monitoring</option>
            </select>

            {/* Severity Filter */}
            <select
              value={selectedSeverity}
              onChange={(e) => setSelectedSeverity(e.target.value)}
              className="rounded-xl border border-slate-300 bg-slate-50 px-3 py-1.5 text-xs font-semibold text-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
            >
              <option value="all">All Severities</option>
              <option value="critical">Critical</option>
              <option value="high">High</option>
              <option value="medium">Medium</option>
              <option value="info">Info</option>
            </select>

            {/* Read/Unread Filter */}
            <div className="inline-flex rounded-xl border border-slate-200 bg-slate-50 p-0.5 text-xs font-semibold">
              <button
                type="button"
                onClick={() => setReadFilter('all')}
                className={`rounded-lg px-2.5 py-1 transition cursor-pointer ${
                  readFilter === 'all' ? 'bg-white text-blue-700 shadow-2xs font-bold' : 'text-slate-500'
                }`}
              >
                All
              </button>
              <button
                type="button"
                onClick={() => setReadFilter('unread')}
                className={`rounded-lg px-2.5 py-1 transition cursor-pointer ${
                  readFilter === 'unread' ? 'bg-white text-blue-700 shadow-2xs font-bold' : 'text-slate-500'
                }`}
              >
                Unread ({unreadCount})
              </button>
              <button
                type="button"
                onClick={() => setReadFilter('read')}
                className={`rounded-lg px-2.5 py-1 transition cursor-pointer ${
                  readFilter === 'read' ? 'bg-white text-blue-700 shadow-2xs font-bold' : 'text-slate-500'
                }`}
              >
                Read
              </button>
            </div>
          </div>

          <span className="text-xs text-slate-500 font-medium">
            Showing <b>{filteredNotifications.length}</b> of {notifications.length} events
          </span>
        </div>
      </div>

      {/* Main Table / List */}
      <SectionCard title="Notification History" subtitle="Live stream of verified events recorded by the SafeVision AI engine.">
        {isLoading && notifications.length === 0 ? (
          <div className="flex flex-col items-center justify-center p-12 text-center">
            <CircularProgress size={32} className="text-blue-600 mb-3" />
            <p className="text-sm font-semibold text-slate-600">Loading notifications...</p>
          </div>
        ) : error ? (
          <div className="rounded-xl border border-rose-200 bg-rose-50/50 p-6 text-center text-xs text-rose-800">
            <p className="font-bold">{error}</p>
            <button
              type="button"
              onClick={() => fetchNotifications(false)}
              className="mt-2 inline-block font-semibold text-blue-600 hover:underline"
            >
              Retry
            </button>
          </div>
        ) : filteredNotifications.length === 0 ? (
          <div className="rounded-xl border border-dashed border-slate-200 bg-slate-50/50 p-12 text-center">
            <CheckCircle2 className="h-10 w-10 text-slate-400 mx-auto mb-2" />
            <h4 className="text-sm font-bold text-slate-800">No notifications match your filters</h4>
            <p className="text-xs text-slate-500 mt-1 max-w-sm mx-auto">
              {readFilter === 'unread'
                ? 'All notifications have been reviewed and marked as read.'
                : 'Events generated during camera monitoring and automated alerts will appear here.'}
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 text-slate-600 border-b border-slate-200">
                <tr>
                  <th className="px-4 py-3 font-semibold">Category</th>
                  <th className="px-4 py-3 font-semibold">Date & Time</th>
                  <th className="px-4 py-3 font-semibold">Title</th>
                  <th className="px-4 py-3 font-semibold">Description</th>
                  <th className="px-4 py-3 font-semibold">Severity</th>
                  <th className="px-4 py-3 font-semibold">Related Entity</th>
                  <th className="px-4 py-3 font-semibold text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {filteredNotifications.map((notif) => (
                  <tr
                    key={notif.id}
                    className={`transition ${
                      !notif.read ? 'bg-blue-50/40 font-medium' : 'hover:bg-slate-50/70'
                    }`}
                  >
                    {/* Category Icon */}
                    <td className="px-4 py-3 whitespace-nowrap">
                      <div className="flex items-center gap-2">
                        <div className="flex h-7 w-7 items-center justify-center rounded-lg border border-slate-200/80 bg-white shadow-2xs">
                          {getCategoryIcon(notif.category)}
                        </div>
                        <span className="capitalize text-[11px] font-semibold text-slate-600">
                          {notif.category}
                        </span>
                      </div>
                    </td>

                    {/* Timestamp */}
                    <td className="px-4 py-3 font-mono text-[11px] text-slate-600 whitespace-nowrap">
                      {notif.datetime || new Date(notif.timestamp * 1000).toLocaleString()}
                    </td>

                    {/* Title */}
                    <td className="px-4 py-3 font-bold text-slate-900 whitespace-nowrap">
                      <div className="flex items-center gap-1.5">
                        {!notif.read && (
                          <span className="h-2 w-2 rounded-full bg-blue-600 shrink-0" />
                        )}
                        <span>{notif.title}</span>
                      </div>
                    </td>

                    {/* Description */}
                    <td className="px-4 py-3 text-slate-600 max-w-md">
                      {notif.description}
                    </td>

                    {/* Severity */}
                    <td className="px-4 py-3 whitespace-nowrap">
                      {getSeverityBadge(notif.severity)}
                    </td>

                    {/* Related Entity */}
                    <td className="px-4 py-3 font-mono text-[11px] text-slate-600 whitespace-nowrap">
                      {notif.incident_id ? (
                        <span className="bg-slate-100 rounded px-1.5 py-0.5 font-bold text-slate-800">
                          {notif.incident_id}
                        </span>
                      ) : notif.worker_id ? (
                        <span>Worker #{notif.worker_id}</span>
                      ) : (
                        <span className="text-slate-400">—</span>
                      )}
                    </td>

                    {/* Actions */}
                    <td className="px-4 py-3 text-right whitespace-nowrap">
                      <div className="flex items-center justify-end gap-2">
                        {!notif.read && (
                          <button
                            type="button"
                            onClick={() => handleMarkAsRead(notif.id)}
                            className="inline-flex items-center gap-1 rounded-lg px-2 py-1 text-[11px] font-semibold text-slate-600 hover:bg-slate-100 hover:text-slate-900 transition cursor-pointer"
                          >
                            <CheckCheck className="h-3 w-3 text-blue-600" />
                            Mark read
                          </button>
                        )}

                        {notif.destination && (
                          <button
                            type="button"
                            onClick={() => {
                              handleMarkAsRead(notif.id);
                              navigate(notif.destination!);
                            }}
                            className="inline-flex items-center gap-1 rounded-lg bg-blue-50 px-2.5 py-1 text-[11px] font-bold text-blue-700 hover:bg-blue-100 transition cursor-pointer"
                          >
                            Inspect
                            <ExternalLink className="h-2.5 w-2.5" />
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </SectionCard>
    </div>
  );
};

export default NotificationsPage;
