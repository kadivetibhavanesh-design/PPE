import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Tooltip, CircularProgress } from '@mui/material';
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
  X,
} from 'lucide-react';
import { notificationService } from '@/services/notificationService';
import { websocketService } from '@/services/websocketService';
import type { AppNotification, NotificationSeverity, NotificationCategory } from '@/types/notification';
import type { WebSocketMessage } from '@/types/monitoring';

function formatRelativeTime(timestamp: number): string {
  const now = Date.now() / 1000;
  const diffSec = Math.max(0, Math.floor(now - timestamp));

  if (diffSec < 15) return 'Just now';
  if (diffSec < 60) return `${diffSec}s ago`;
  const diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `${diffHr}h ago`;
  const diffDays = Math.floor(diffHr / 24);
  if (diffDays === 1) return 'Yesterday';
  if (diffDays < 7) return `${diffDays}d ago`;
  return new Date(timestamp * 1000).toLocaleDateString();
}

function getCategoryIcon(category: NotificationCategory) {
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
}

function getSeverityBadge(severity: NotificationSeverity) {
  switch (severity) {
    case 'critical':
      return (
        <span className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wider bg-rose-100 text-rose-800 border border-rose-200">
          <ShieldAlert className="h-2.5 w-2.5" />
          Critical
        </span>
      );
    case 'high':
      return (
        <span className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wider bg-orange-100 text-orange-800 border border-orange-200">
          <AlertTriangle className="h-2.5 w-2.5" />
          High
        </span>
      );
    case 'medium':
      return (
        <span className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wider bg-amber-100 text-amber-800 border border-amber-200">
          <AlertTriangle className="h-2.5 w-2.5" />
          Medium
        </span>
      );
    default:
      return (
        <span className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wider bg-blue-100 text-blue-800 border border-blue-200">
          <Info className="h-2.5 w-2.5" />
          Info
        </span>
      );
  }
}

export const NotificationCenter: React.FC = () => {
  const navigate = useNavigate();
  const [isOpen, setIsOpen] = useState<boolean>(false);
  const [notifications, setNotifications] = useState<AppNotification[]>([]);
  const [unreadCount, setUnreadCount] = useState<number>(0);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [isClearing, setIsClearing] = useState<boolean>(false);
  const [isMarkingAll, setIsMarkingAll] = useState<boolean>(false);
  const [filterMode, setFilterMode] = useState<'all' | 'unread'>('all');

  const panelRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);

  // Fetch notifications from backend
  const fetchNotifications = useCallback(async (quiet = false) => {
    if (!quiet) setIsLoading(true);
    setError(null);
    try {
      const data = await notificationService.getNotifications({ limit: 40 });
      setNotifications(data.notifications);
      setUnreadCount(data.unread_count);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to load notifications';
      setError(msg);
    } finally {
      if (!quiet) setIsLoading(false);
    }
  }, []);

  // Initial fetch and interval fallback poll
  useEffect(() => {
    fetchNotifications(true);
    const timer = setInterval(() => {
      fetchNotifications(true);
    }, 12000);
    return () => clearInterval(timer);
  }, [fetchNotifications]);

  // Real-time WebSocket listener
  useEffect(() => {
    const handleWsMessage = (msg: WebSocketMessage) => {
      if (msg.type === 'notification' && msg.data) {
        const newNotif = msg.data;
        setNotifications((prev) => {
          // Prevent duplicates by ID
          if (prev.some((n) => n.id === newNotif.id)) return prev;
          return [newNotif, ...prev];
        });
        setUnreadCount((c) => c + 1);
      }
    };

    const unsubscribe = websocketService.onMessage(handleWsMessage);
    return () => unsubscribe();
  }, []);

  // Close dropdown on click outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        isOpen &&
        panelRef.current &&
        !panelRef.current.contains(event.target as Node) &&
        buttonRef.current &&
        !buttonRef.current.contains(event.target as Node)
      ) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [isOpen]);

  // Mark single notification as read and navigate
  const handleNotificationClick = async (notif: AppNotification) => {
    if (!notif.read) {
      try {
        await notificationService.markAsRead(notif.id);
        setNotifications((prev) =>
          prev.map((n) => (n.id === notif.id ? { ...n, read: true } : n))
        );
        setUnreadCount((c) => Math.max(0, c - 1));
      } catch (err) {
        console.error('Failed to mark notification as read:', err);
      }
    }

    if (notif.destination) {
      setIsOpen(false);
      navigate(notif.destination);
    }
  };

  // Mark all as read
  const handleMarkAllRead = async (e: React.MouseEvent) => {
    e.stopPropagation();
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

  // Clear all notifications with confirmation
  const handleClearAll = async (e: React.MouseEvent) => {
    e.stopPropagation();
    if (notifications.length === 0 || isClearing) return;
    if (!window.confirm('Clear all notifications from history?')) return;

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

  const displayedNotifications =
    filterMode === 'unread' ? notifications.filter((n) => !n.read) : notifications;

  return (
    <div className="relative inline-block">
      {/* Bell Button */}
      <Tooltip title={unreadCount > 0 ? `${unreadCount} unread notification${unreadCount === 1 ? '' : 's'}` : 'Notifications'}>
        <button
          ref={buttonRef}
          type="button"
          onClick={() => {
            setIsOpen((prev) => !prev);
            if (!isOpen) fetchNotifications(true);
          }}
          aria-label="Open notifications center"
          aria-expanded={isOpen}
          className={`relative flex h-9 w-9 items-center justify-center rounded-full transition-all cursor-pointer ${
            isOpen
              ? 'bg-blue-100 text-blue-700 ring-2 ring-blue-500/30'
              : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
          }`}
        >
          <Bell className="h-5 w-5" />
          {unreadCount > 0 && (
            <span className="absolute -top-1 -right-1 flex h-5 min-w-5 items-center justify-center rounded-full bg-rose-600 px-1 text-[11px] font-black text-white shadow-xs animate-in zoom-in-75">
              {unreadCount > 99 ? '99+' : unreadCount}
            </span>
          )}
        </button>
      </Tooltip>

      {/* Notification Dropdown Panel */}
      {isOpen && (
        <div
          ref={panelRef}
          className="absolute right-0 mt-2 z-50 w-84 sm:w-96 rounded-2xl border border-slate-200/80 bg-white/95 backdrop-blur-md shadow-2xl transition-all animate-in fade-in slide-in-from-top-2"
          role="dialog"
          aria-label="Notifications Center"
        >
          {/* Header */}
          <div className="flex items-center justify-between border-b border-slate-100 p-4">
            <div className="flex items-center gap-2">
              <h3 className="text-sm font-bold text-slate-900">Notifications</h3>
              {unreadCount > 0 && (
                <span className="rounded-full bg-blue-100 px-2 py-0.5 text-[11px] font-bold text-blue-800">
                  {unreadCount} new
                </span>
              )}
            </div>

            <div className="flex items-center gap-1">
              {unreadCount > 0 && (
                <Tooltip title="Mark all as read">
                  <button
                    type="button"
                    onClick={handleMarkAllRead}
                    disabled={isMarkingAll}
                    aria-label="Mark all notifications as read"
                    className="inline-flex items-center gap-1 rounded-lg px-2 py-1 text-xs font-semibold text-slate-600 hover:bg-slate-100 hover:text-slate-900 transition cursor-pointer"
                  >
                    {isMarkingAll ? (
                      <CircularProgress size={12} color="inherit" />
                    ) : (
                      <CheckCheck className="h-3.5 w-3.5 text-blue-600" />
                    )}
                    <span className="hidden sm:inline">Read all</span>
                  </button>
                </Tooltip>
              )}

              {notifications.length > 0 && (
                <Tooltip title="Clear history">
                  <button
                    type="button"
                    onClick={handleClearAll}
                    disabled={isClearing}
                    aria-label="Clear all notifications"
                    className="inline-flex items-center rounded-lg p-1 text-slate-400 hover:bg-rose-50 hover:text-rose-600 transition cursor-pointer"
                  >
                    {isClearing ? (
                      <CircularProgress size={12} color="inherit" />
                    ) : (
                      <Trash2 className="h-3.5 w-3.5" />
                    )}
                  </button>
                </Tooltip>
              )}

              <button
                type="button"
                onClick={() => setIsOpen(false)}
                aria-label="Close notification panel"
                className="rounded-lg p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600 transition cursor-pointer"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          </div>

          {/* Filter Bar */}
          <div className="flex items-center justify-between border-b border-slate-100 bg-slate-50/50 px-4 py-2">
            <div className="flex gap-1.5">
              <button
                type="button"
                onClick={() => setFilterMode('all')}
                className={`rounded-lg px-2.5 py-1 text-xs font-semibold transition cursor-pointer ${
                  filterMode === 'all'
                    ? 'bg-white text-blue-700 shadow-2xs font-bold'
                    : 'text-slate-500 hover:text-slate-900'
                }`}
              >
                All ({notifications.length})
              </button>
              <button
                type="button"
                onClick={() => setFilterMode('unread')}
                className={`rounded-lg px-2.5 py-1 text-xs font-semibold transition cursor-pointer ${
                  filterMode === 'unread'
                    ? 'bg-white text-blue-700 shadow-2xs font-bold'
                    : 'text-slate-500 hover:text-slate-900'
                }`}
              >
                Unread ({unreadCount})
              </button>
            </div>

            <button
              type="button"
              onClick={() => fetchNotifications(false)}
              disabled={isLoading}
              title="Refresh notifications"
              className="rounded-md p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600 transition cursor-pointer"
            >
              <RefreshCw className={`h-3 w-3 ${isLoading ? 'animate-spin' : ''}`} />
            </button>
          </div>

          {/* Notification List Scrollport */}
          <div className="max-h-96 overflow-y-auto divide-y divide-slate-100">
            {isLoading && notifications.length === 0 ? (
              <div className="flex flex-col items-center justify-center p-8 text-center">
                <CircularProgress size={24} className="text-blue-600 mb-2" />
                <span className="text-xs text-slate-500">Loading notifications...</span>
              </div>
            ) : error ? (
              <div className="p-6 text-center">
                <AlertTriangle className="h-6 w-6 text-rose-500 mx-auto mb-2" />
                <p className="text-xs font-semibold text-rose-700">{error}</p>
                <button
                  type="button"
                  onClick={() => fetchNotifications(false)}
                  className="mt-2 text-xs font-bold text-blue-600 hover:underline"
                >
                  Retry
                </button>
              </div>
            ) : displayedNotifications.length === 0 ? (
              <div className="flex flex-col items-center justify-center p-8 text-center">
                <div className="flex h-12 w-12 items-center justify-center rounded-full bg-slate-100 text-slate-400 mb-2">
                  <CheckCircle2 className="h-6 w-6 text-slate-400" />
                </div>
                <p className="text-xs font-bold text-slate-700">No notifications</p>
                <p className="text-[11px] text-slate-400 mt-0.5">
                  {filterMode === 'unread'
                    ? 'All notifications have been read.'
                    : 'Live safety alerts and monitoring updates will appear here.'}
                </p>
              </div>
            ) : (
              displayedNotifications.map((notif) => (
                <div
                  key={notif.id}
                  onClick={() => handleNotificationClick(notif)}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      handleNotificationClick(notif);
                    }
                  }}
                  className={`group relative flex items-start gap-3 p-3.5 transition cursor-pointer select-none ${
                    !notif.read
                      ? 'bg-blue-50/50 hover:bg-blue-50/80 font-medium'
                      : 'hover:bg-slate-50/80'
                  }`}
                >
                  {/* Category Icon */}
                  <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-xl border border-slate-200/80 bg-white shadow-2xs">
                    {getCategoryIcon(notif.category)}
                  </div>

                  {/* Content */}
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center justify-between gap-1.5 mb-1">
                      <p className={`text-xs truncate ${!notif.read ? 'font-bold text-slate-900' : 'font-semibold text-slate-700'}`}>
                        {notif.title}
                      </p>
                      <Tooltip title={notif.datetime || new Date(notif.timestamp * 1000).toLocaleString()}>
                        <span className="shrink-0 font-mono text-[10px] text-slate-400">
                          {formatRelativeTime(notif.timestamp)}
                        </span>
                      </Tooltip>
                    </div>

                    <p className="text-[11px] leading-relaxed text-slate-600 line-clamp-2">
                      {notif.description}
                    </p>

                    <div className="mt-2 flex items-center justify-between gap-2">
                      <div className="flex items-center gap-1.5">
                        {getSeverityBadge(notif.severity)}
                        {notif.incident_id && (
                          <span className="font-mono text-[10px] font-semibold text-slate-500 bg-slate-100 rounded px-1.5 py-0.5">
                            {notif.incident_id}
                          </span>
                        )}
                      </div>

                      {notif.destination && (
                        <span className="inline-flex items-center gap-1 text-[10px] font-bold text-blue-600 group-hover:underline">
                          View details
                          <ExternalLink className="h-2.5 w-2.5" />
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Unread Indicator Dot */}
                  {!notif.read && (
                    <span
                      className="mt-1 h-2 w-2 shrink-0 rounded-full bg-blue-600"
                      title="Unread notification"
                    />
                  )}
                </div>
              ))
            )}
          </div>

          {/* Footer: View All Action */}
          <div className="border-t border-slate-100 bg-slate-50/80 p-2.5 text-center rounded-b-2xl">
            <button
              type="button"
              onClick={() => {
                setIsOpen(false);
                navigate('/notifications');
              }}
              className="inline-flex items-center justify-center gap-1.5 w-full rounded-xl py-1.5 text-xs font-bold text-blue-600 hover:bg-blue-50 transition cursor-pointer"
            >
              View All Notifications
              <ExternalLink className="h-3 w-3" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default NotificationCenter;
