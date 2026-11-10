import { useEffect, useState, useRef, useCallback } from 'react';
import {
  Cpu,
  Camera,
  ShieldCheck,
  Bell,
  Mail,
  Send,
  Eye,
  EyeOff,
  AtSign,
  Activity,
  HardDrive,
  Sliders,
  Server,
  CheckCircle2,
  AlertTriangle,
  RefreshCw,
  Volume2,
  VolumeX,
  Trash2,
  Save,
  RotateCcw,
  Info,
  Clock,
  Sparkles,
  Zap,
} from 'lucide-react';
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from 'recharts';

import SectionCard from '@/components/SectionCard';
import StatusPill from '@/components/StatusPill';
import { settingsService } from '@/services/settingsService';
import { monitoringService } from '@/services/monitoringService';
import { emailService } from '@/services/emailService';
import type {
  FullSettings,
  SanitizedModelsResponse,
  CameraTestResult,
  CameraDeviceItem,
  SystemMetrics,
  SystemInfoData,
} from '@/types/settings';
import type {
  EmailSettings,
  EmailStatus,
  EmailHistoryRecord,
} from '@/types/email';

type SettingsTab =
  | 'model'
  | 'camera'
  | 'ppe'
  | 'alerts'
  | 'email'
  | 'health'
  | 'storage'
  | 'preferences'
  | 'info';

interface MetricPoint {
  time: string;
  cpu: number;
  ram: number;
  latency: number;
  fps: number;
}

export default function SettingsPage() {
  const [activeTab, setActiveTab] = useState<SettingsTab>('model');

  // Core settings state
  const [settings, setSettings] = useState<FullSettings | null>(null);
  const [modelProfilesData, setModelProfilesData] = useState<SanitizedModelsResponse | null>(null);
  const [selectedProfileId, setSelectedProfileId] = useState<string>('constructelligence');
  const [isMonitoringActive, setIsMonitoringActive] = useState<boolean>(false);

  // Status & Feedback
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isSaving, setIsSaving] = useState<boolean>(false);
  const [isSwitchingModel, setIsSwitchingModel] = useState<boolean>(false);
  const [feedback, setFeedback] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  // Camera Testing state
  const [cameraTestResult, setCameraTestResult] = useState<CameraTestResult | null>(null);
  const [isTestingCamera, setIsTestingCamera] = useState<boolean>(false);
  const [cameraDevices, setCameraDevices] = useState<CameraDeviceItem[]>([]);
  const [isScanningDevices, setIsScanningDevices] = useState<boolean>(false);

  // Audio Testing state
  const [isTestingAudio, setIsTestingAudio] = useState<boolean>(false);
  const [isStoppingAlarms, setIsStoppingAlarms] = useState<boolean>(false);

  // System Health & Metrics state
  const [metrics, setMetrics] = useState<SystemMetrics | null>(null);
  const [metricsHistory, setMetricsHistory] = useState<MetricPoint[]>([]);

  // System Info & Storage cleanup state
  const [systemInfo, setSystemInfo] = useState<SystemInfoData | null>(null);
  const [isCleaningStorage, setIsCleaningStorage] = useState<boolean>(false);
  const [showCleanupModal, setShowCleanupModal] = useState<boolean>(false);
  const [showResetModal, setShowResetModal] = useState<boolean>(false);

  // Email Notifications state
  const [emailForm, setEmailForm] = useState<EmailSettings>({
    enabled: false,
    recipient_email: 'bhavaneshkadiveti@gmail.com',
    sender_email: '',
    smtp_host: 'smtp.gmail.com',
    smtp_port: 587,
    smtp_username: '',
    smtp_password: '',
    has_password: false,
    use_tls: true,
    use_ssl: false,
    reminder_interval_minutes: 5,
  });
  const [emailStatus, setEmailStatus] = useState<EmailStatus | null>(null);
  const [emailHistory, setEmailHistory] = useState<EmailHistoryRecord[]>([]);
  const [currentEpochSec, setCurrentEpochSec] = useState<number>(() => Math.floor(Date.now() / 1000));
  const [isSavingEmail, setIsSavingEmail] = useState<boolean>(false);
  const [isSendingTestEmail, setIsSendingTestEmail] = useState<boolean>(false);
  const [isLoadingEmailHistory, setIsLoadingEmailHistory] = useState<boolean>(false);
  const [showPassword, setShowPassword] = useState<boolean>(false);
  const [testRecipientModal, setTestRecipientModal] = useState<boolean>(false);
  const [customTestEmail, setCustomTestEmail] = useState<string>('');

  // Polling ref
  const pollingRef = useRef<number | null>(null);

  // Fetch initial data
  const loadAllData = useCallback(async () => {
    setIsLoading(true);
    setFeedback(null);
    try {
      const [fullCfg, modelsRes, statusRes, infoRes, emailCfg] = await Promise.all([
        settingsService.getAllSettings(),
        settingsService.getModelProfiles(),
        monitoringService.getStatus().catch(() => null),
        settingsService.getSystemInfo().catch(() => null),
        emailService.getEmailSettings().catch(() => null),
      ]);

      setSettings(fullCfg);
      setModelProfilesData(modelsRes);
      setSelectedProfileId(modelsRes.active_profile_id);
      setIsMonitoringActive(statusRes?.is_running ?? false);
      if (infoRes) setSystemInfo(infoRes);
      if (emailCfg) setEmailForm(emailCfg);
    } catch (err: unknown) {
      console.error('Failed to load settings data:', err);
      const msg = err instanceof Error ? err.message : 'Failed to retrieve configuration from backend.';
      setFeedback({ type: 'error', message: msg });
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadAllData();
  }, [loadAllData]);

  // System Health Polling (active only on 'health' tab)
  useEffect(() => {
    if (activeTab !== 'health') {
      if (pollingRef.current) clearInterval(pollingRef.current);
      return;
    }

    const fetchMetrics = async () => {
      try {
        const m = await settingsService.getSystemMetrics();
        setMetrics(m);
        const timeStr = new Date(m.timestamp * 1000).toLocaleTimeString([], {
          hour: '2-digit',
          minute: '2-digit',
          second: '2-digit',
        });

        setMetricsHistory((prev) => {
          const next = [
            ...prev,
            {
              time: timeStr,
              cpu: m.cpu.percent,
              ram: m.ram.percent,
              latency: m.ai_pipeline.latest_inference_latency_ms,
              fps: m.ai_pipeline.fps,
            },
          ];
          return next.slice(-20); // Keep last 20 readings
        });
      } catch (err) {
        console.error('Failed to fetch system metrics:', err);
      }
    };

    fetchMetrics();
    const interval = window.setInterval(fetchMetrics, 3000);
    pollingRef.current = interval;

    return () => {
      clearInterval(interval);
    };
  }, [activeTab]);

  // Email Tab Polling (refreshes live status & reminder schedules every 5s while on email tab)
  useEffect(() => {
    if (activeTab !== 'email') return;

    let isMounted = true;
    const fetchEmailData = async () => {
      try {
        setCurrentEpochSec(Math.floor(Date.now() / 1000));
        const [statusRes, historyRes] = await Promise.all([
          emailService.getEmailStatus().catch(() => null),
          emailService.getEmailHistory(50).catch(() => null),
        ]);
        if (!isMounted) return;
        if (statusRes) setEmailStatus(statusRes);
        if (historyRes) setEmailHistory(historyRes.history);
      } catch (err) {
        console.error('Failed to poll email notification status:', err);
      }
    };

    fetchEmailData();
    const interval = window.setInterval(fetchEmailData, 5000);

    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, [activeTab]);

  const isValidEmailAddress = (email: string): boolean => {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim());
  };

  const handleSaveEmailSettings = async () => {
    if (!isValidEmailAddress(emailForm.recipient_email)) {
      setFeedback({
        type: 'error',
        message: 'Invalid recipient email address format. Please enter a valid email address (e.g. user@domain.com).',
      });
      return;
    }

    setIsSavingEmail(true);
    setIsSaving(true);
    setFeedback(null);
    try {
      const res = await emailService.updateEmailSettings(emailForm);
      const updated = res.settings || res.email;
      if (res.success && updated) {
        setEmailForm((prev) => ({
          ...prev,
          ...updated,
          smtp_password: prev.smtp_password === '******' ? '******' : (updated.smtp_password || prev.smtp_password),
        }));
        if (settings) {
          setSettings((prev) => (prev ? { ...prev, email: updated } : prev));
        }
        setFeedback({
          type: 'success',
          message: 'Email notification configuration saved and applied to live scheduler.',
        });
        const updatedStatus = await emailService.getEmailStatus().catch(() => null);
        if (updatedStatus) setEmailStatus(updatedStatus);
      } else {
        setFeedback({
          type: 'error',
          message: 'Failed to update email settings: Invalid response from backend.',
        });
      }
    } catch (err: unknown) {
      console.error('Failed to save email settings:', err);
      const msg = err instanceof Error ? err.message : 'Failed to save email notification settings.';
      setFeedback({ type: 'error', message: msg });
    } finally {
      setIsSavingEmail(false);
      setIsSaving(false);
    }
  };

  const handleSendTestEmail = async (targetEmail?: string) => {
    const recipient = (targetEmail || customTestEmail || emailForm.recipient_email).trim();
    if (!isValidEmailAddress(recipient)) {
      setFeedback({
        type: 'error',
        message: 'Cannot send test email: Invalid recipient email address.',
      });
      return;
    }

    setIsSendingTestEmail(true);
    setFeedback(null);
    try {
      const res = await emailService.sendTestEmail(recipient);
      if (res.success) {
        setFeedback({
          type: 'success',
          message: res.message || `Test email dispatched successfully to ${recipient}.`,
        });
      } else {
        setFeedback({
          type: 'error',
          message: 'Unable to deliver test email. Please check your email configuration and recipient address.',
        });
      }
      const [statusRes, historyRes] = await Promise.all([
        emailService.getEmailStatus().catch(() => null),
        emailService.getEmailHistory(50).catch(() => null),
      ]);
      if (statusRes) setEmailStatus(statusRes);
      if (historyRes) setEmailHistory(historyRes.history);
    } catch {
      setFeedback({
        type: 'error',
        message: 'Unable to deliver test email. Please check your email configuration and recipient address.',
      });
    } finally {
      setIsSendingTestEmail(false);
      setTestRecipientModal(false);
    }
  };

  const handleRefreshEmailHistory = async () => {
    setIsLoadingEmailHistory(true);
    try {
      const hist = await emailService.getEmailHistory(100);
      setEmailHistory(hist.history);
    } catch (err) {
      console.error('Failed to refresh history:', err);
    } finally {
      setIsLoadingEmailHistory(false);
    }
  };

  // Save Settings handler
  const handleSaveSettings = async () => {
    if (activeTab === 'email') {
      await handleSaveEmailSettings();
      return;
    }
    if (!settings) return;
    setIsSaving(true);
    setFeedback(null);
    try {
      const res = await settingsService.updateSettings(settings);
      setSettings(res.settings);
      if (res.settings?.email) {
        setEmailForm((prev) => ({
          ...prev,
          ...res.settings.email!,
          smtp_password: prev.smtp_password === '******' ? '******' : (res.settings.email!.smtp_password || prev.smtp_password),
        }));
      }
      setFeedback({ type: 'success', message: 'Configuration saved and applied to live services.' });
    } catch (err: unknown) {
      console.error('Failed to persist settings:', err);
      const msg = err instanceof Error ? err.message : 'Failed to persist settings.';
      setFeedback({ type: 'error', message: msg });
    } finally {
      setIsSaving(false);
    }
  };

  // Reset to Defaults handler
  const handleResetDefaults = async () => {
    setIsSaving(true);
    setShowResetModal(false);
    setFeedback(null);
    try {
      const res = await settingsService.resetToDefaults();
      setSettings(res.settings);
      const modelsRes = await settingsService.getModelProfiles();
      setModelProfilesData(modelsRes);
      setSelectedProfileId(modelsRes.active_profile_id);
      setFeedback({ type: 'success', message: 'All system settings have been reset to factory defaults.' });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to reset settings to defaults.';
      setFeedback({ type: 'error', message: msg });
    } finally {
      setIsSaving(false);
    }
  };

  // Model Profile Activation
  const handleActivateModel = async (profileId: string) => {
    if (isMonitoringActive) {
      setFeedback({
        type: 'error',
        message: 'Camera monitoring is currently running. Stop monitoring before activating a different model.',
      });
      return;
    }

    setIsSwitchingModel(true);
    setFeedback(null);
    try {
      const res = await settingsService.activateModelProfile(profileId);
      if (res.success) {
        const modelsRes = await settingsService.getModelProfiles();
        setModelProfilesData(modelsRes);
        setSelectedProfileId(profileId);
        setFeedback({ type: 'success', message: res.message });
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to activate detection model profile.';
      setFeedback({ type: 'error', message: msg });
    } finally {
      setIsSwitchingModel(false);
    }
  };

  // Safe Camera Test
  const handleTestCamera = async () => {
    if (!settings) return;
    setIsTestingCamera(true);
    setCameraTestResult(null);
    try {
      const res = await settingsService.testCamera(
        settings.camera.device_index,
        settings.camera.backend
      );
      setCameraTestResult(res);
    } catch (err: unknown) {
      setCameraTestResult({
        success: false,
        available: false,
        in_use: false,
        message: err instanceof Error ? err.message : 'Camera test request failed.',
      });
    } finally {
      setIsTestingCamera(false);
    }
  };

  // Scan Camera Devices
  const handleScanDevices = async () => {
    setIsScanningDevices(true);
    try {
      const devs = await settingsService.scanCameraDevices();
      setCameraDevices(devs);
    } catch (err) {
      console.error('Failed to scan camera devices:', err);
    } finally {
      setIsScanningDevices(false);
    }
  };

  // Audio Test
  const handleTestAudio = async () => {
    if (!settings) return;
    setIsTestingAudio(true);
    try {
      await settingsService.testAlarmTone(
        settings.alerts.duration_ms,
        settings.alerts.frequency_hz
      );
    } catch (err) {
      console.error('Test audio error:', err);
    } finally {
      setTimeout(() => setIsTestingAudio(false), 500);
    }
  };

  // Stop All Alarms
  const handleStopAllAlarms = async () => {
    setIsStoppingAlarms(true);
    try {
      const res = await settingsService.stopAllAlarms();
      setFeedback({ type: 'success', message: res.message });
    } catch (err) {
      console.error('Stop alarms error:', err);
    } finally {
      setIsStoppingAlarms(false);
    }
  };

  // Cleanup Expired Evidence
  const handleCleanupEvidence = async () => {
    if (!settings) return;
    setIsCleaningStorage(true);
    setShowCleanupModal(false);
    try {
      const res = await settingsService.cleanupEvidence(settings.storage.retention_days);
      setFeedback({
        type: 'success',
        message: `Purged ${res.removed_count} evidence files (${res.freed_mb} MB freed).`,
      });
      // Refresh metrics
      if (activeTab === 'health') {
        const m = await settingsService.getSystemMetrics();
        setMetrics(m);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to purge expired evidence.';
      setFeedback({ type: 'error', message: msg });
    } finally {
      setIsCleaningStorage(false);
    }
  };

  // Helper for setting mutations
  const updateSettingsField = <T extends keyof FullSettings>(
    section: T,
    field: keyof FullSettings[T],
    value: FullSettings[T][keyof FullSettings[T]]
  ) => {
    if (!settings) return;
    setSettings({
      ...settings,
      [section]: {
        ...settings[section],
        [field]: value,
      },
    });
  };

  const navItems = [
    { id: 'model', label: 'AI Model', icon: Cpu },
    { id: 'camera', label: 'Camera', icon: Camera },
    { id: 'ppe', label: 'PPE Detection', icon: ShieldCheck },
    { id: 'alerts', label: 'Alerts & Audio', icon: Bell },
    { id: 'email', label: 'Email Alerts', icon: Mail },
    { id: 'health', label: 'System Health', icon: Activity },
    { id: 'storage', label: 'Storage & Evidence', icon: HardDrive },
    { id: 'preferences', label: 'Preferences', icon: Sliders },
    { id: 'info', label: 'System Info', icon: Server },
  ] as const;

  return (
    <div className="space-y-6">
      {/* 1. Page Header & Actions Bar */}
      <div className="glass-card rounded-2xl p-5 sm:p-6 shadow-sm border border-slate-200/80 bg-white/95">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="space-y-1">
            <div className="flex items-center gap-2.5">
              <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-brand-50 text-brand-600 border border-brand-200/60">
                <Sliders className="h-5 w-5" />
              </div>
              <h2 className="text-2xl font-bold tracking-tight text-slate-900">System Settings</h2>
            </div>
            <p className="text-sm text-slate-500">
              Manage detection profiles, camera hardware, spatial association rules, alerts, and system health.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2.5">
            <button
              type="button"
              onClick={loadAllData}
              disabled={isLoading || isSaving}
              className="inline-flex items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-3.5 py-2 text-xs font-semibold text-slate-700 shadow-2xs transition hover:bg-slate-50 disabled:opacity-50"
            >
              <RefreshCw className={`h-3.5 w-3.5 ${isLoading ? 'animate-spin' : ''}`} />
              Reload
            </button>

            <button
              type="button"
              onClick={() => setShowResetModal(true)}
              disabled={isLoading || isSaving}
              className="inline-flex items-center gap-1.5 rounded-xl border border-rose-200 bg-rose-50/60 px-3.5 py-2 text-xs font-semibold text-rose-700 shadow-2xs transition hover:bg-rose-100/70 disabled:opacity-50"
            >
              <RotateCcw className="h-3.5 w-3.5" />
              Reset Defaults
            </button>

            <button
              type="button"
              onClick={handleSaveSettings}
              disabled={isLoading || isSaving || isSavingEmail}
              className="inline-flex items-center gap-1.5 rounded-xl bg-brand-600 px-4 py-2 text-xs font-semibold text-white shadow-xs transition hover:bg-brand-700 disabled:opacity-50"
            >
              <Save className={`h-3.5 w-3.5 ${isSaving || isSavingEmail ? 'animate-spin' : ''}`} />
              {isSaving || isSavingEmail ? 'Applying...' : 'Save Changes'}
            </button>
          </div>
        </div>

        {/* Navigation Tabs */}
        <div className="mt-6 flex overflow-x-auto border-b border-slate-200 no-scrollbar gap-1 sm:gap-2">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = activeTab === item.id;
            return (
              <button
                key={item.id}
                type="button"
                onClick={() => setActiveTab(item.id)}
                className={`inline-flex shrink-0 items-center gap-2 border-b-2 px-3.5 py-2.5 text-xs font-semibold transition-all ${
                  isActive
                    ? 'border-brand-600 text-brand-700 bg-brand-50/50 rounded-t-lg'
                    : 'border-transparent text-slate-600 hover:border-slate-300 hover:text-slate-900'
                }`}
              >
                <Icon className={`h-4 w-4 ${isActive ? 'text-brand-600' : 'text-slate-400'}`} />
                {item.label}
              </button>
            );
          })}
        </div>
      </div>

      {/* Global Feedback Banner */}
      {feedback && (
        <div
          className={`flex items-start gap-2.5 rounded-xl border p-4 text-xs shadow-2xs transition-all ${
            feedback.type === 'success'
              ? 'border-emerald-200 bg-emerald-50 text-emerald-800'
              : 'border-rose-200 bg-rose-50 text-rose-800'
          }`}
        >
          {feedback.type === 'success' ? (
            <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-600 mt-0.5" />
          ) : (
            <AlertTriangle className="h-4 w-4 shrink-0 text-rose-600 mt-0.5" />
          )}
          <span className="font-medium">{feedback.message}</span>
        </div>
      )}

      {/* Live Monitoring Active Alert Banner */}
      {isMonitoringActive && (
        <div className="flex items-start gap-2.5 rounded-xl border border-amber-200 bg-amber-50/90 p-4 text-xs text-amber-800 shadow-2xs">
          <AlertTriangle className="h-4 w-4 shrink-0 text-amber-600 mt-0.5" />
          <div>
            <p className="font-semibold text-amber-900">Live Camera Monitoring is Running</p>
            <p className="mt-0.5 text-amber-700">
              AI model profile switching is safely locked while the camera inference thread is active. Stop monitoring from the Live Monitoring page to switch detection profiles.
            </p>
          </div>
        </div>
      )}

      {/* =========================================================================
          SECTION 1: AI MODEL CONFIGURATION
          ========================================================================= */}
      {activeTab === 'model' && (
        <div className="space-y-6">
          <SectionCard
            title="AI Detection Model Configuration"
            subtitle="Select and activate specialized real-time PPE detection profiles."
          >
            <div className="space-y-6">
              <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
                {modelProfilesData?.profiles.map((profile) => {
                  const isSelected = selectedProfileId === profile.profile_id;
                  const isActive = profile.is_active;

                  return (
                    <div
                      key={profile.profile_id}
                      onClick={() => !isMonitoringActive && setSelectedProfileId(profile.profile_id)}
                      className={`relative flex flex-col justify-between rounded-2xl border p-5 transition-all cursor-pointer ${
                        isSelected
                          ? 'border-brand-500 bg-brand-50/20 shadow-md ring-2 ring-brand-500/20'
                          : 'border-slate-200 bg-white hover:border-slate-300 hover:shadow-xs'
                      } ${isMonitoringActive ? 'cursor-not-allowed opacity-85' : ''}`}
                    >
                      <div className="space-y-3">
                        <div className="flex items-start justify-between gap-2">
                          <div className="flex items-center gap-3">
                            <div
                              className={`flex h-10 w-10 items-center justify-center rounded-xl shadow-2xs ${
                                isActive
                                  ? 'bg-emerald-600 text-white'
                                  : 'bg-slate-100 text-slate-600'
                              }`}
                            >
                              <Cpu className="h-5 w-5" />
                            </div>
                            <div>
                              <h3 className="text-base font-bold text-slate-900">{profile.name}</h3>
                              <p className="text-[11px] font-medium text-slate-500">
                                {profile.profile_id === 'constructelligence'
                                  ? '14 Hazard Classes'
                                  : '10 PPE Classes'}
                              </p>
                            </div>
                          </div>
                          <div>
                            {isActive ? (
                              <StatusPill tone="green">Currently Active</StatusPill>
                            ) : (
                              <StatusPill tone="slate">Inactive</StatusPill>
                            )}
                          </div>
                        </div>

                        <p className="text-xs text-slate-600 leading-relaxed">{profile.description}</p>

                        <div className="space-y-2 pt-2 border-t border-slate-100 text-xs">
                          <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
                            Detection Capabilities
                          </div>
                          <ul className="space-y-1.5">
                            {profile.capabilities.map((cap, i) => (
                              <li key={i} className="flex items-center gap-2 text-slate-700">
                                <Sparkles className="h-3.5 w-3.5 text-brand-500 shrink-0" />
                                <span>{cap}</span>
                              </li>
                            ))}
                          </ul>
                        </div>

                        <div className="pt-2 border-t border-slate-100 text-xs space-y-1.5">
                          <div className="flex items-center justify-between">
                            <span className="text-slate-500">Positive Face Mask Verification:</span>
                            {profile.positive_mask_support ? (
                              <span className="font-semibold text-emerald-700 inline-flex items-center gap-1">
                                <CheckCircle2 className="h-3.5 w-3.5" /> Full Verification
                              </span>
                            ) : (
                              <span className="font-medium text-amber-700 inline-flex items-center gap-1">
                                <Info className="h-3.5 w-3.5" /> Violation Only (Missing)
                              </span>
                            )}
                          </div>

                          <div className="flex items-center justify-between">
                            <span className="text-slate-500">Target Environment:</span>
                            <span className="font-medium text-slate-700 text-right">{profile.recommended_for}</span>
                          </div>
                        </div>
                      </div>

                      <div className="mt-6 pt-4 border-t border-slate-100">
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            handleActivateModel(profile.profile_id);
                          }}
                          disabled={
                            isMonitoringActive ||
                            isActive ||
                            isSwitchingModel
                          }
                          className="w-full inline-flex items-center justify-center gap-2 rounded-xl bg-brand-600 px-4 py-2.5 text-xs font-semibold text-white shadow-xs transition hover:bg-brand-700 disabled:bg-slate-200 disabled:text-slate-400 disabled:cursor-not-allowed"
                        >
                          {isSwitchingModel && isSelected ? (
                            <>
                              <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                              Activating Profile...
                            </>
                          ) : isActive ? (
                            <>
                              <CheckCircle2 className="h-3.5 w-3.5" />
                              Active Profile
                            </>
                          ) : (
                            <>
                              <Zap className="h-3.5 w-3.5" />
                              Activate This Profile
                            </>
                          )}
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </SectionCard>
        </div>
      )}

      {/* =========================================================================
          SECTION 2: CAMERA CONFIGURATION
          ========================================================================= */}
      {activeTab === 'camera' && settings && (
        <div className="space-y-6">
          <SectionCard
            title="Camera & Hardware Video Capture"
            subtitle="Configure local video capture indices, resolutions, and test camera connectivity safely without starting background monitoring."
          >
            <div className="space-y-6">
              <div className="grid grid-cols-1 gap-5 md:grid-cols-2 lg:grid-cols-4">
                {/* Camera Device Index */}
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                    Camera Device Index
                  </label>
                  <div className="flex gap-2">
                    <select
                      value={settings.camera.device_index}
                      onChange={(e) =>
                        updateSettingsField('camera', 'device_index', parseInt(e.target.value, 10))
                      }
                      className="w-full rounded-xl border border-slate-300 bg-white px-3.5 py-2.5 text-xs font-semibold text-slate-900 shadow-2xs transition focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20"
                    >
                      <option value={0}>Camera 0 (Default / Built-in)</option>
                      <option value={1}>Camera 1 (Secondary / External USB)</option>
                      <option value={2}>Camera 2 (Auxiliary)</option>
                      <option value={3}>Camera 3 (Industrial RTSP/Capture)</option>
                    </select>
                  </div>
                </div>

                {/* Resolution */}
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                    Frame Resolution
                  </label>
                  <select
                    value={settings.camera.resolution}
                    onChange={(e) => {
                      const val = e.target.value;
                      const [w, h] = val.split('x').map(Number);
                      setSettings({
                        ...settings,
                        camera: {
                          ...settings.camera,
                          resolution: val,
                          width: w,
                          height: h,
                        },
                      });
                    }}
                    className="w-full rounded-xl border border-slate-300 bg-white px-3.5 py-2.5 text-xs font-semibold text-slate-900 shadow-2xs transition focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20"
                  >
                    <option value="1280x720">1280x720 (720p HD - Recommended)</option>
                    <option value="1920x1080">1920x1080 (1080p Full HD)</option>
                    <option value="640x480">640x480 (VGA Low Latency)</option>
                  </select>
                </div>

                {/* Target Frame Rate */}
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                    Target Frame Rate (FPS)
                  </label>
                  <select
                    value={settings.camera.fps}
                    onChange={(e) =>
                      updateSettingsField('camera', 'fps', parseInt(e.target.value, 10))
                    }
                    className="w-full rounded-xl border border-slate-300 bg-white px-3.5 py-2.5 text-xs font-semibold text-slate-900 shadow-2xs transition focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20"
                  >
                    <option value={30}>30 FPS (Standard Smooth)</option>
                    <option value={25}>25 FPS (PAL Standard)</option>
                    <option value={20}>20 FPS (Optimized CPU)</option>
                    <option value={15}>15 FPS (Resource Constrained)</option>
                  </select>
                </div>

                {/* Backend API */}
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                    Capture Backend
                  </label>
                  <select
                    value={settings.camera.backend}
                    onChange={(e) =>
                      updateSettingsField('camera', 'backend', e.target.value)
                    }
                    className="w-full rounded-xl border border-slate-300 bg-white px-3.5 py-2.5 text-xs font-semibold text-slate-900 shadow-2xs transition focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20"
                  >
                    <option value="DirectShow">DirectShow (Windows Accelerated)</option>
                    <option value="Default">Default OS API</option>
                  </select>
                </div>
              </div>

              {/* Action & Test Controls */}
              <div className="flex flex-wrap items-center gap-3 pt-2">
                <button
                  type="button"
                  onClick={handleTestCamera}
                  disabled={isTestingCamera}
                  className="inline-flex items-center gap-2 rounded-xl bg-slate-900 px-4 py-2.5 text-xs font-semibold text-white shadow-2xs transition hover:bg-slate-800 disabled:opacity-50"
                >
                  <Camera className={`h-3.5 w-3.5 ${isTestingCamera ? 'animate-spin' : ''}`} />
                  {isTestingCamera ? 'Testing Availability...' : 'Test Camera Availability'}
                </button>

                <button
                  type="button"
                  onClick={handleScanDevices}
                  disabled={isScanningDevices}
                  className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-xs font-semibold text-slate-700 shadow-2xs transition hover:bg-slate-50 disabled:opacity-50"
                >
                  <RefreshCw className={`h-3.5 w-3.5 ${isScanningDevices ? 'animate-spin' : ''}`} />
                  {isScanningDevices ? 'Scanning Hardware...' : 'Scan Connected Devices'}
                </button>
              </div>

              {/* Camera Test Feedback Box */}
              {cameraTestResult && (
                <div
                  className={`rounded-xl border p-4 text-xs shadow-2xs ${
                    cameraTestResult.available
                      ? 'border-emerald-200 bg-emerald-50/90 text-emerald-900'
                      : 'border-rose-200 bg-rose-50/90 text-rose-900'
                  }`}
                >
                  <div className="flex items-start gap-2.5">
                    {cameraTestResult.available ? (
                      <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-600 mt-0.5" />
                    ) : (
                      <AlertTriangle className="h-4 w-4 shrink-0 text-rose-600 mt-0.5" />
                    )}
                    <div className="space-y-1">
                      <p className="font-semibold">{cameraTestResult.message}</p>
                      {cameraTestResult.available && (
                        <div className="flex flex-wrap gap-4 text-[11px] text-emerald-700 mt-1">
                          <span>Verified Resolution: <b>{cameraTestResult.resolution}</b></span>
                          <span>Hardware FPS: <b>{cameraTestResult.fps} FPS</b></span>
                          {cameraTestResult.latency_ms && (
                            <span>Hardware Probe Latency: <b>{cameraTestResult.latency_ms} ms</b></span>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              )}

              {/* Scanned Devices List */}
              {cameraDevices.length > 0 && (
                <div className="rounded-xl border border-slate-200 bg-slate-50/50 p-4 text-xs space-y-2">
                  <span className="font-semibold text-slate-700 block">Detected Video Devices:</span>
                  <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                    {cameraDevices.map((dev) => (
                      <div
                        key={dev.index}
                        className="flex items-center justify-between p-2.5 rounded-lg border border-slate-200 bg-white text-xs"
                      >
                        <span className="font-medium text-slate-800">{dev.name}</span>
                        {dev.in_use ? (
                          <StatusPill tone="blue">In Active Use</StatusPill>
                        ) : dev.available ? (
                          <StatusPill tone="green">Available</StatusPill>
                        ) : (
                          <StatusPill tone="slate">Not Detected</StatusPill>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </SectionCard>
        </div>
      )}

      {/* =========================================================================
          SECTION 3: PPE DETECTION CONFIGURATION
          ========================================================================= */}
      {activeTab === 'ppe' && settings && (
        <div className="space-y-6">
          <SectionCard
            title="PPE Detection & Spatial Association Rules"
            subtitle="Configure confidence thresholds, minimum intersection-over-area (IoA), and continuous duration timers."
          >
            <div className="space-y-8">
              {/* Global Threshold Sliders */}
              <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-4">
                {/* Global Confidence */}
                <div className="space-y-2 p-4 rounded-xl border border-slate-200 bg-slate-50/40">
                  <div className="flex justify-between items-center text-xs">
                    <span className="font-semibold text-slate-700">Global Detection Confidence</span>
                    <span className="font-bold text-brand-600 bg-brand-50 px-2 py-0.5 rounded-md border border-brand-200">
                      {(settings.ppe.global_confidence * 100).toFixed(0)}%
                    </span>
                  </div>
                  <input
                    type="range"
                    min={0.10}
                    max={0.90}
                    step={0.05}
                    value={settings.ppe.global_confidence}
                    onChange={(e) =>
                      updateSettingsField('ppe', 'global_confidence', parseFloat(e.target.value))
                    }
                    className="w-full accent-brand-600 cursor-pointer"
                  />
                  <p className="text-[11px] text-slate-500">
                    Baseline threshold below which YOLO PPE detections are rejected.
                  </p>
                </div>

                {/* Worker Association Min IoA */}
                <div className="space-y-2 p-4 rounded-xl border border-slate-200 bg-slate-50/40">
                  <div className="flex justify-between items-center text-xs">
                    <span className="font-semibold text-slate-700">Worker Association Min IoA</span>
                    <span className="font-bold text-brand-600 bg-brand-50 px-2 py-0.5 rounded-md border border-brand-200">
                      {settings.ppe.min_ioa.toFixed(2)}
                    </span>
                  </div>
                  <input
                    type="range"
                    min={0.05}
                    max={0.50}
                    step={0.01}
                    value={settings.ppe.min_ioa}
                    onChange={(e) =>
                      updateSettingsField('ppe', 'min_ioa', parseFloat(e.target.value))
                    }
                    className="w-full accent-brand-600 cursor-pointer"
                  />
                  <p className="text-[11px] text-slate-500">
                    Minimum overlap required to associate a detected PPE item with a person.
                  </p>
                </div>

                {/* Continuous Violation Duration */}
                <div className="space-y-2 p-4 rounded-xl border border-slate-200 bg-slate-50/40">
                  <div className="flex justify-between items-center text-xs">
                    <span className="font-semibold text-slate-700">Violation Duration Threshold</span>
                    <span className="font-bold text-brand-600 bg-brand-50 px-2 py-0.5 rounded-md border border-brand-200">
                      {settings.ppe.violation_duration.toFixed(1)}s
                    </span>
                  </div>
                  <input
                    type="range"
                    min={1.0}
                    max={20.0}
                    step={0.5}
                    value={settings.ppe.violation_duration}
                    onChange={(e) =>
                      updateSettingsField('ppe', 'violation_duration', parseFloat(e.target.value))
                    }
                    className="w-full accent-brand-600 cursor-pointer"
                  />
                  <p className="text-[11px] text-slate-500">
                    Continuous seconds a PPE item must be missing before raising an alarm.
                  </p>
                </div>

                {/* Violation Cooldown */}
                <div className="space-y-2 p-4 rounded-xl border border-slate-200 bg-slate-50/40">
                  <div className="flex justify-between items-center text-xs">
                    <span className="font-semibold text-slate-700">Alarm Re-Trigger Cooldown</span>
                    <span className="font-bold text-brand-600 bg-brand-50 px-2 py-0.5 rounded-md border border-brand-200">
                      {settings.ppe.violation_cooldown.toFixed(1)}s
                    </span>
                  </div>
                  <input
                    type="range"
                    min={5.0}
                    max={60.0}
                    step={1.0}
                    value={settings.ppe.violation_cooldown}
                    onChange={(e) =>
                      updateSettingsField('ppe', 'violation_cooldown', parseFloat(e.target.value))
                    }
                    className="w-full accent-brand-600 cursor-pointer"
                  />
                  <p className="text-[11px] text-slate-500">
                    Interval before the same continuous violation can sound an alarm again.
                  </p>
                </div>
              </div>

              {/* Per-PPE Category Configuration Cards */}
              <div className="space-y-4">
                <h4 className="text-sm font-bold text-slate-900">Per-Category Enforcement & Confidence</h4>
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
                  {[
                    { key: 'hardhat', label: 'Hardhat / Helmet', note: 'Compliant & Missing' },
                    { key: 'safety_vest', label: 'High-Visibility Safety Vest', note: 'Compliant & Missing' },
                    { key: 'mask', label: 'Face Mask / Respirator', note: 'Profile Dependent' },
                    { key: 'gloves', label: 'Safety Hand Gloves', note: 'Compliant & Missing' },
                    { key: 'goggles', label: 'Eye Protection Goggles', note: 'Compliant & Missing' },
                  ].map((cat) => {
                    const isEnabled = settings.ppe.enabled_categories.includes(cat.key);
                    const catConf = settings.ppe.category_confidence[cat.key] ?? settings.ppe.global_confidence;

                    return (
                      <div
                        key={cat.key}
                        className="rounded-xl border border-slate-200 bg-white p-4 shadow-2xs space-y-3"
                      >
                        <div className="flex items-center justify-between">
                          <span className="text-xs font-bold text-slate-900">{cat.label}</span>
                          <label className="relative inline-flex items-center cursor-pointer">
                            <input
                              type="checkbox"
                              checked={isEnabled}
                              onChange={(e) => {
                                const nextCats = e.target.checked
                                  ? [...settings.ppe.enabled_categories, cat.key]
                                  : settings.ppe.enabled_categories.filter((c) => c !== cat.key);
                                updateSettingsField('ppe', 'enabled_categories', nextCats);
                              }}
                              className="sr-only peer"
                            />
                            <div className="w-9 h-5 bg-slate-200 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-brand-600"></div>
                          </label>
                        </div>

                        <div className="flex items-center justify-between text-[11px] text-slate-500">
                          <span>Detection Scope:</span>
                          <span className="font-semibold text-slate-700">{cat.note}</span>
                        </div>

                        <div className="space-y-1.5 pt-2 border-t border-slate-100">
                          <div className="flex justify-between text-[11px]">
                            <span className="text-slate-500">Category Confidence:</span>
                            <span className="font-bold text-slate-900">{(catConf * 100).toFixed(0)}%</span>
                          </div>
                          <input
                            type="range"
                            min={0.10}
                            max={0.90}
                            step={0.05}
                            value={catConf}
                            disabled={!isEnabled}
                            onChange={(e) => {
                              const val = parseFloat(e.target.value);
                              setSettings({
                                ...settings,
                                ppe: {
                                  ...settings.ppe,
                                  category_confidence: {
                                    ...settings.ppe.category_confidence,
                                    [cat.key]: val,
                                  },
                                },
                              });
                            }}
                            className="w-full accent-brand-600 cursor-pointer disabled:opacity-40"
                          />
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          </SectionCard>
        </div>
      )}

      {/* =========================================================================
          SECTION 4: ALERT & NOTIFICATION SETTINGS
          ========================================================================= */}
      {activeTab === 'alerts' && settings && (
        <div className="space-y-6">
          <SectionCard
            title="Audio Alarms & Visual Notifications"
            subtitle="Configure synthesized alarm tone frequency, playback duration, visual warning banners, and test audio hardware."
          >
            <div className="space-y-6">
              {/* Master Toggles */}
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <div className="flex items-center justify-between p-4 rounded-xl border border-slate-200 bg-white shadow-2xs">
                  <div className="space-y-0.5">
                    <span className="text-xs font-bold text-slate-900">Audio Alarm Output</span>
                    <p className="text-[11px] text-slate-500">Play local synthesized alarm sound on confirmed violations.</p>
                  </div>
                  <label className="relative inline-flex items-center cursor-pointer">
                    <input
                      type="checkbox"
                      checked={settings.alerts.sound_enabled}
                      onChange={(e) =>
                        updateSettingsField('alerts', 'sound_enabled', e.target.checked)
                      }
                      className="sr-only peer"
                    />
                    <div className="w-10 h-6 bg-slate-200 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-brand-600"></div>
                  </label>
                </div>

                <div className="flex items-center justify-between p-4 rounded-xl border border-slate-200 bg-white shadow-2xs">
                  <div className="space-y-0.5">
                    <span className="text-xs font-bold text-slate-900">Visual Screen Warnings</span>
                    <p className="text-[11px] text-slate-500">Display pulsating red banners and bounding-box alerts.</p>
                  </div>
                  <label className="relative inline-flex items-center cursor-pointer">
                    <input
                      type="checkbox"
                      checked={settings.alerts.visual_enabled}
                      onChange={(e) =>
                        updateSettingsField('alerts', 'visual_enabled', e.target.checked)
                      }
                      className="sr-only peer"
                    />
                    <div className="w-10 h-6 bg-slate-200 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-brand-600"></div>
                  </label>
                </div>
              </div>

              {/* Sliders for Tone and Frequency */}
              <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
                <div className="space-y-2 p-4 rounded-xl border border-slate-200 bg-slate-50/40">
                  <div className="flex justify-between items-center text-xs">
                    <span className="font-semibold text-slate-700">Alarm Duration</span>
                    <span className="font-bold text-brand-600 bg-brand-50 px-2 py-0.5 rounded-md border border-brand-200">
                      {settings.alerts.duration_ms} ms
                    </span>
                  </div>
                  <input
                    type="range"
                    min={100}
                    max={2000}
                    step={50}
                    value={settings.alerts.duration_ms}
                    onChange={(e) =>
                      updateSettingsField('alerts', 'duration_ms', parseInt(e.target.value, 10))
                    }
                    className="w-full accent-brand-600 cursor-pointer"
                  />
                  <p className="text-[11px] text-slate-500">Audio playback length per alarm burst.</p>
                </div>

                <div className="space-y-2 p-4 rounded-xl border border-slate-200 bg-slate-50/40">
                  <div className="flex justify-between items-center text-xs">
                    <span className="font-semibold text-slate-700">Audio Frequency</span>
                    <span className="font-bold text-brand-600 bg-brand-50 px-2 py-0.5 rounded-md border border-brand-200">
                      {settings.alerts.frequency_hz} Hz
                    </span>
                  </div>
                  <input
                    type="range"
                    min={400}
                    max={2500}
                    step={50}
                    value={settings.alerts.frequency_hz}
                    onChange={(e) =>
                      updateSettingsField('alerts', 'frequency_hz', parseInt(e.target.value, 10))
                    }
                    className="w-full accent-brand-600 cursor-pointer"
                  />
                  <p className="text-[11px] text-slate-500">Pitch tone (1000 Hz is standard industrial alert tone).</p>
                </div>

                <div className="space-y-2 p-4 rounded-xl border border-slate-200 bg-slate-50/40">
                  <div className="flex justify-between items-center text-xs">
                    <span className="font-semibold text-slate-700">Violation Alert Cooldown</span>
                    <span className="font-bold text-brand-600 bg-brand-50 px-2 py-0.5 rounded-md border border-brand-200">
                      {settings.alerts.cooldown_seconds}s
                    </span>
                  </div>
                  <input
                    type="range"
                    min={5.0}
                    max={60.0}
                    step={1.0}
                    value={settings.alerts.cooldown_seconds}
                    onChange={(e) =>
                      updateSettingsField('alerts', 'cooldown_seconds', parseFloat(e.target.value))
                    }
                    className="w-full accent-brand-600 cursor-pointer"
                  />
                  <p className="text-[11px] text-slate-500">Minimum quiet interval between sound alerts for ongoing continuous violation.</p>
                </div>
              </div>

              {/* Action Buttons */}
              <div className="flex flex-wrap items-center gap-3 pt-2">
                <button
                  type="button"
                  onClick={handleTestAudio}
                  disabled={isTestingAudio}
                  className="inline-flex items-center gap-2 rounded-xl bg-slate-900 px-4 py-2.5 text-xs font-semibold text-white shadow-2xs transition hover:bg-slate-800 disabled:opacity-50"
                >
                  <Volume2 className={`h-3.5 w-3.5 ${isTestingAudio ? 'animate-bounce' : ''}`} />
                  {isTestingAudio ? 'Playing Tone...' : 'Test Alarm Tone'}
                </button>

                <button
                  type="button"
                  onClick={handleStopAllAlarms}
                  disabled={isStoppingAlarms}
                  className="inline-flex items-center gap-2 rounded-xl border border-rose-200 bg-rose-50 px-4 py-2.5 text-xs font-semibold text-rose-700 shadow-2xs transition hover:bg-rose-100 disabled:opacity-50"
                >
                  <VolumeX className="h-3.5 w-3.5" />
                  {isStoppingAlarms ? 'Silencing...' : 'Stop All Active Alarms'}
                </button>
              </div>
            </div>
          </SectionCard>
        </div>
      )}

      {/* =========================================================================
          SECTION: AUTOMATIC EMAIL ALERTS & REMINDERS
          ========================================================================= */}
      {activeTab === 'email' && (
        <div className="space-y-6">
          {/* Card 1: Configuration Form */}
          <SectionCard
            title="Automatic Email Alert & Ongoing Reminder Configuration"
            subtitle="Configure recipient inbox, SMTP credentials, and continuous violation reminder intervals."
          >
            <div className="space-y-6">
              {/* Global Enable Toggle */}
              <div className="flex items-center justify-between p-4 rounded-xl border border-slate-200 bg-slate-50/60">
                <div className="space-y-0.5">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-bold text-slate-900">Enable Automatic Email Notifications</span>
                    <span
                      className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                        emailForm.enabled
                          ? 'bg-emerald-100 text-emerald-700'
                          : 'bg-slate-200 text-slate-600'
                      }`}
                    >
                      {emailForm.enabled ? 'ACTIVE' : 'DISABLED'}
                    </span>
                  </div>
                  <p className="text-xs text-slate-500">
                    Dispatches a First Alert immediately after a PPE violation is confirmed continuous for 5 seconds, followed by recurring reminders every 5 minutes until resolved.
                  </p>
                </div>
                <label className="relative inline-flex items-center cursor-pointer">
                  <input
                    type="checkbox"
                    checked={emailForm.enabled}
                    onChange={(e) =>
                      setEmailForm((prev) => ({ ...prev, enabled: e.target.checked }))
                    }
                    className="sr-only peer"
                  />
                  <div className="w-11 h-6 bg-slate-200 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-brand-600"></div>
                </label>
              </div>

              {/* Primary Recipient Email */}
              <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-2xs space-y-3">
                <div className="flex items-center justify-between">
                  <div>
                    <label className="text-xs font-bold text-slate-900 flex items-center gap-1.5">
                      <AtSign className="h-4 w-4 text-brand-600" />
                      Primary Violation Notification Recipient
                    </label>
                    <p className="text-[11px] text-slate-500 mt-0.5">
                      All confirmed PPE incident First Alerts and recurring ongoing reminders will be delivered to this address.
                    </p>
                  </div>
                  {isValidEmailAddress(emailForm.recipient_email) ? (
                    <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-emerald-700 bg-emerald-50 px-2.5 py-1 rounded-md border border-emerald-200">
                      <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600" />
                      Valid Email Format
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-rose-700 bg-rose-50 px-2.5 py-1 rounded-md border border-rose-200">
                      <AlertTriangle className="h-3.5 w-3.5 text-rose-600" />
                      Invalid Email Format
                    </span>
                  )}
                </div>

                <div className="relative">
                  <input
                    type="email"
                    value={emailForm.recipient_email}
                    onChange={(e) =>
                      setEmailForm((prev) => ({ ...prev, recipient_email: e.target.value }))
                    }
                    placeholder="bhavaneshkadiveti@gmail.com"
                    className="w-full rounded-xl border border-slate-200 bg-white px-3.5 py-2.5 text-sm font-medium text-slate-900 shadow-2xs transition focus:border-brand-500 focus:outline-hidden focus:ring-2 focus:ring-brand-500/20"
                  />
                </div>
                <p className="text-[11px] text-slate-400">
                  Default recipient: <code className="text-slate-600 bg-slate-100 px-1.5 py-0.5 rounded">bhavaneshkadiveti@gmail.com</code>. Stored locally in backend configuration.
                </p>
              </div>

              {/* Sender & Reminder Interval */}
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                {/* Sender Email */}
                <div className="space-y-1.5 rounded-xl border border-slate-200 bg-white p-4 shadow-2xs">
                  <label className="text-xs font-bold text-slate-900">Sender Email (From header)</label>
                  <input
                    type="text"
                    value={emailForm.sender_email || ''}
                    onChange={(e) =>
                      setEmailForm((prev) => ({ ...prev, sender_email: e.target.value }))
                    }
                    placeholder="alerts@safevision.ai (or leave empty for SMTP user)"
                    className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-medium text-slate-900 shadow-2xs focus:border-brand-500 focus:outline-hidden"
                  />
                  <p className="text-[11px] text-slate-500">
                    Displayed sender address on outgoing notification emails.
                  </p>
                </div>

                {/* Reminder Interval */}
                <div className="space-y-1.5 rounded-xl border border-slate-200 bg-white p-4 shadow-2xs">
                  <label className="text-xs font-bold text-slate-900 flex items-center justify-between">
                    <span>Ongoing Reminder Interval</span>
                    <span className="text-[11px] font-bold text-brand-600 bg-brand-50 px-2 py-0.5 rounded border border-brand-200">
                      {emailForm.reminder_interval_minutes} minutes
                    </span>
                  </label>
                  <select
                    value={emailForm.reminder_interval_minutes}
                    onChange={(e) =>
                      setEmailForm((prev) => ({
                        ...prev,
                        reminder_interval_minutes: parseInt(e.target.value, 10),
                      }))
                    }
                    className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-medium text-slate-900 shadow-2xs focus:border-brand-500 focus:outline-hidden"
                  >
                    <option value={1}>1 minute (Testing / Fast Cadence)</option>
                    <option value={2}>2 minutes</option>
                    <option value={5}>5 minutes (Standard Industrial Default)</option>
                    <option value={10}>10 minutes</option>
                    <option value={15}>15 minutes</option>
                    <option value={30}>30 minutes</option>
                    <option value={60}>60 minutes (1 Hour)</option>
                  </select>
                  <p className="text-[11px] text-slate-500">
                    Recurring interval for reminder emails while an incident remains unresolved.
                  </p>
                </div>
              </div>

              {/* SMTP Connection Configuration */}
              <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-2xs space-y-4">
                <div className="flex items-center justify-between border-b border-slate-100 pb-3">
                  <div>
                    <h4 className="text-xs font-bold text-slate-900 uppercase tracking-wide">
                      SMTP Relay Configuration
                    </h4>
                    <p className="text-[11px] text-slate-500">
                      Outgoing mail server connection settings (Gmail SMTP supported).
                    </p>
                  </div>
                  {emailStatus?.smtp_configured ? (
                    <span className="text-[11px] font-semibold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-md border border-emerald-200">
                      SMTP Configured
                    </span>
                  ) : (
                    <span className="text-[11px] font-semibold text-amber-700 bg-amber-50 px-2 py-0.5 rounded-md border border-amber-200">
                      Credentials Required
                    </span>
                  )}
                </div>

                <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
                  {/* SMTP Host */}
                  <div className="space-y-1.5 sm:col-span-2">
                    <label className="text-xs font-semibold text-slate-700">SMTP Host Server</label>
                    <input
                      type="text"
                      value={emailForm.smtp_host}
                      onChange={(e) =>
                        setEmailForm((prev) => ({ ...prev, smtp_host: e.target.value }))
                      }
                      placeholder="smtp.gmail.com"
                      className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-medium text-slate-900 shadow-2xs focus:border-brand-500 focus:outline-hidden"
                    />
                    <p className="text-[10px] text-slate-400">e.g. smtp.gmail.com or mail.internal-site.com</p>
                  </div>

                  {/* SMTP Port */}
                  <div className="space-y-1.5">
                    <label className="text-xs font-semibold text-slate-700">Port Number</label>
                    <input
                      type="number"
                      value={emailForm.smtp_port}
                      onChange={(e) =>
                        setEmailForm((prev) => ({
                          ...prev,
                          smtp_port: parseInt(e.target.value, 10) || 587,
                        }))
                      }
                      placeholder="587"
                      className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-medium text-slate-900 shadow-2xs focus:border-brand-500 focus:outline-hidden"
                    />
                    <p className="text-[10px] text-slate-400">587 (STARTTLS) or 465 (SSL)</p>
                  </div>
                </div>

                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                  {/* SMTP Username */}
                  <div className="space-y-1.5">
                    <label className="text-xs font-semibold text-slate-700">SMTP Username / Login Email</label>
                    <input
                      type="text"
                      value={emailForm.smtp_username || ''}
                      onChange={(e) =>
                        setEmailForm((prev) => ({ ...prev, smtp_username: e.target.value }))
                      }
                      placeholder="your-email@gmail.com"
                      className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-medium text-slate-900 shadow-2xs focus:border-brand-500 focus:outline-hidden"
                    />
                    <p className="text-[10px] text-slate-400">Your Google or mail account username.</p>
                  </div>

                  {/* SMTP App Password */}
                  <div className="space-y-1.5">
                    <div className="flex items-center justify-between">
                      <label className="text-xs font-semibold text-slate-700">SMTP App Password</label>
                      {emailForm.has_password && (
                        <span className="text-[10px] font-bold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
                          Password Stored
                        </span>
                      )}
                    </div>
                    <div className="relative">
                      <input
                        type={showPassword ? 'text' : 'password'}
                        value={emailForm.smtp_password || ''}
                        onChange={(e) =>
                          setEmailForm((prev) => ({ ...prev, smtp_password: e.target.value }))
                        }
                        placeholder={emailForm.has_password ? '****** (Leave blank to keep)' : 'Enter 16-char app password'}
                        className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 pr-10 text-xs font-medium text-slate-900 shadow-2xs focus:border-brand-500 focus:outline-hidden"
                      />
                      <button
                        type="button"
                        onClick={() => setShowPassword(!showPassword)}
                        className="absolute right-2.5 top-2.5 text-slate-400 hover:text-slate-600"
                        title={showPassword ? 'Hide password' : 'Show password'}
                      >
                        {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                      </button>
                    </div>
                    <p className="text-[10px] text-slate-400">Never exposed in plain-text API responses.</p>
                  </div>
                </div>

                {/* TLS & SSL Checkboxes */}
                <div className="flex flex-wrap gap-6 pt-2">
                  <label className="inline-flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={emailForm.use_tls}
                      onChange={(e) =>
                        setEmailForm((prev) => ({ ...prev, use_tls: e.target.checked }))
                      }
                      className="rounded border-slate-300 text-brand-600 focus:ring-brand-500"
                    />
                    <span className="text-xs font-medium text-slate-700">Enable STARTTLS (Recommended for Port 587)</span>
                  </label>

                  <label className="inline-flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={emailForm.use_ssl}
                      onChange={(e) =>
                        setEmailForm((prev) => ({ ...prev, use_ssl: e.target.checked }))
                      }
                      className="rounded border-slate-300 text-brand-600 focus:ring-brand-500"
                    />
                    <span className="text-xs font-medium text-slate-700">Enable Direct SSL/TLS (Port 465)</span>
                  </label>
                </div>

                {/* Google App Password Guidance */}
                <div className="rounded-xl border border-blue-200 bg-blue-50/70 p-4 space-y-1.5">
                  <div className="flex items-center gap-2 text-xs font-bold text-blue-900">
                    <Info className="h-4 w-4 text-blue-600 shrink-0" />
                    How to generate a Gmail SMTP App Password:
                  </div>
                  <ol className="text-[11px] text-blue-800 list-decimal list-inside space-y-0.5 pl-1 leading-relaxed">
                    <li>Go to your <b>Google Account</b> &gt; <b>Security</b>.</li>
                    <li>Ensure <b>2-Step Verification</b> is turned ON.</li>
                    <li>Search for <b>App passwords</b> (or visit <code>myaccount.google.com/apppasswords</code>).</li>
                    <li>Create an app named <code>SafeVision AI</code> and copy the generated 16-character code.</li>
                    <li>Paste the 16-character code into the <b>SMTP App Password</b> field above and click Save.</li>
                  </ol>
                </div>
              </div>

              {/* Action Buttons */}
              <div className="flex flex-wrap items-center justify-between gap-3 pt-2">
                <div className="flex flex-wrap items-center gap-2.5">
                  <button
                    type="button"
                    onClick={handleSaveEmailSettings}
                    disabled={isSavingEmail || isSaving}
                    className="inline-flex items-center gap-2 rounded-xl bg-brand-600 px-4 py-2.5 text-xs font-semibold text-white shadow-xs transition hover:bg-brand-700 disabled:opacity-50"
                  >
                    <Save className={`h-3.5 w-3.5 ${isSavingEmail || isSaving ? 'animate-spin' : ''}`} />
                    {isSavingEmail || isSaving ? 'Saving Settings...' : 'Save Email Configuration'}
                  </button>

                  <button
                    type="button"
                    onClick={() => handleSendTestEmail()}
                    disabled={isSendingTestEmail || !emailForm.recipient_email}
                    className="inline-flex items-center gap-2 rounded-xl bg-slate-900 px-4 py-2.5 text-xs font-semibold text-white shadow-2xs transition hover:bg-slate-800 disabled:opacity-50"
                  >
                    <Send className={`h-3.5 w-3.5 ${isSendingTestEmail ? 'animate-spin' : ''}`} />
                    {isSendingTestEmail ? 'Dispatching Test Email...' : 'Send Test Email'}
                  </button>

                  <button
                    type="button"
                    onClick={() => {
                      setCustomTestEmail(emailForm.recipient_email);
                      setTestRecipientModal(true);
                    }}
                    disabled={isSendingTestEmail}
                    className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-3.5 py-2.5 text-xs font-semibold text-slate-700 shadow-2xs transition hover:bg-slate-50 disabled:opacity-50"
                  >
                    <Mail className="h-3.5 w-3.5 text-slate-500" />
                    Test Custom Recipient...
                  </button>
                </div>

                <div className="text-[11px] text-slate-500">
                  Evidence images attached automatically from local storage.
                </div>
              </div>
            </div>
          </SectionCard>

          {/* Card 2: Live Status & Active Incident Schedules */}
          <SectionCard
            title="Live Email Scheduler Engine & Ongoing Violation Schedules"
            subtitle="Real-time monitoring of continuous violation timers and independent reminder dispatch schedules."
          >
            <div className="space-y-6">
              {/* Stat Tiles */}
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
                {/* Engine Status */}
                <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-2xs space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold text-slate-500">Engine State</span>
                    <span
                      className={`text-[10px] font-bold px-2 py-0.5 rounded-md ${
                        emailStatus?.enabled
                          ? emailStatus?.smtp_configured
                            ? 'bg-emerald-100 text-emerald-700'
                            : 'bg-amber-100 text-amber-700'
                          : 'bg-slate-100 text-slate-600'
                      }`}
                    >
                      {emailStatus?.enabled
                        ? emailStatus?.smtp_configured
                          ? 'READY'
                          : 'SMTP NEEDED'
                        : 'DISABLED'}
                    </span>
                  </div>
                  <p className="text-xl font-black text-slate-900">
                    {emailStatus?.enabled ? 'Operational' : 'Disabled'}
                  </p>
                  <p className="text-[11px] text-slate-500 pt-1 border-t border-slate-100 truncate">
                    To: {emailStatus?.recipient_email || 'None'}
                  </p>
                </div>

                {/* Total Delivered */}
                <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-2xs space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold text-slate-500">Emails Dispatched</span>
                    <span className="text-[10px] font-bold px-2 py-0.5 rounded-md bg-brand-100 text-brand-700">
                      SUCCESS
                    </span>
                  </div>
                  <p className="text-xl font-black text-slate-900">{emailStatus?.total_emails_sent ?? 0}</p>
                  <p className="text-[11px] text-slate-500 pt-1 border-t border-slate-100">
                    {emailStatus?.last_sent_timestamp
                      ? `Last: ${new Date(emailStatus.last_sent_timestamp * 1000).toLocaleTimeString()}`
                      : 'No emails dispatched yet'}
                  </p>
                </div>

                {/* Failed Deliveries */}
                <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-2xs space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold text-slate-500">Delivery Failures</span>
                    <span
                      className={`text-[10px] font-bold px-2 py-0.5 rounded-md ${
                        (emailStatus?.failed_email_count ?? 0) > 0
                          ? 'bg-rose-100 text-rose-700'
                          : 'bg-emerald-100 text-emerald-700'
                      }`}
                    >
                      {(emailStatus?.failed_email_count ?? 0) > 0 ? 'ATTENTION' : 'CLEAN'}
                    </span>
                  </div>
                  <p className="text-xl font-black text-slate-900">{emailStatus?.failed_email_count ?? 0}</p>
                  <p className="text-[11px] text-slate-500 pt-1 border-t border-slate-100">
                    Auto-retry on transient errors
                  </p>
                </div>

                {/* Active Incident Schedules Count */}
                <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-2xs space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold text-slate-500">Active Schedules</span>
                    <span
                      className={`text-[10px] font-bold px-2 py-0.5 rounded-md ${
                        (emailStatus?.active_incident_schedules_count ?? 0) > 0
                          ? 'bg-amber-100 text-amber-700 animate-pulse'
                          : 'bg-emerald-100 text-emerald-700'
                      }`}
                    >
                      {(emailStatus?.active_incident_schedules_count ?? 0) > 0 ? 'TRACKING' : 'IDLE'}
                    </span>
                  </div>
                  <p className="text-xl font-black text-slate-900">
                    {emailStatus?.active_incident_schedules_count ?? 0}
                  </p>
                  <p className="text-[11px] text-slate-500 pt-1 border-t border-slate-100">
                    Cadence: every {emailStatus?.reminder_interval_minutes ?? 5}m
                  </p>
                </div>
              </div>



              {/* Active Incident Schedules Table */}
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <h4 className="text-xs font-bold text-slate-900 uppercase tracking-wide">
                    Ongoing Incident Reminder Schedules
                  </h4>
                  <span className="text-xs text-slate-500">
                    Auto-cancels immediately when worker corrects PPE
                  </span>
                </div>

                {(emailStatus?.active_incident_schedules && emailStatus.active_incident_schedules.length > 0) ? (
                  <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
                    <table className="w-full text-left text-xs">
                      <thead className="bg-slate-50 text-slate-600 border-b border-slate-200">
                        <tr>
                          <th className="px-4 py-3 font-semibold">Incident ID</th>
                          <th className="px-4 py-3 font-semibold">Worker</th>
                          <th className="px-4 py-3 font-semibold">Missing PPE</th>
                          <th className="px-4 py-3 font-semibold">Status</th>
                          <th className="px-4 py-3 font-semibold">First Alert</th>
                          <th className="px-4 py-3 font-semibold">Reminders Sent</th>
                          <th className="px-4 py-3 font-semibold">Next Reminder In</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100">
                        {emailStatus.active_incident_schedules.map((sch) => {
                          const nowSec = currentEpochSec;
                          const nextSec = sch.next_reminder_timestamp ? Math.max(0, Math.round(sch.next_reminder_timestamp - nowSec)) : 0;
                          const nextMin = Math.floor(nextSec / 60);
                          const nextSecRem = nextSec % 60;
                          const nextDueStr = sch.next_reminder_timestamp
                            ? nextSec > 0
                              ? `${nextMin}m ${nextSecRem}s`
                              : 'Due now'
                            : 'N/A';

                          return (
                            <tr key={sch.incident_id} className="hover:bg-slate-50/70">
                              <td className="px-4 py-3 font-mono font-bold text-slate-900">
                                {sch.incident_id}
                              </td>
                              <td className="px-4 py-3 font-semibold text-slate-800">
                                Worker #{sch.worker_track_id}
                              </td>
                              <td className="px-4 py-3 font-semibold text-rose-600 capitalize">
                                {sch.ppe_category.replace('_', ' ')}
                              </td>
                              <td className="px-4 py-3">
                                <span className="inline-block px-2 py-0.5 rounded text-[10px] font-bold uppercase bg-amber-100 text-amber-800">
                                  {sch.status}
                                </span>
                              </td>
                              <td className="px-4 py-3">
                                <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-emerald-700">
                                  <CheckCircle2 className="h-3 w-3 text-emerald-600" />
                                  Sent
                                </span>
                              </td>
                              <td className="px-4 py-3 font-bold text-slate-900">
                                #{sch.reminder_count}
                              </td>
                              <td className="px-4 py-3 font-semibold text-brand-700">
                                {nextDueStr}
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <div className="rounded-xl border border-dashed border-slate-200 bg-slate-50/50 p-6 text-center">
                    <ShieldCheck className="mx-auto h-8 w-8 text-emerald-500 mb-2" />
                    <p className="text-xs font-bold text-slate-800">No Active Incident Reminder Schedules</p>
                    <p className="text-[11px] text-slate-500 mt-0.5 max-w-md mx-auto">
                      All workers currently monitored are compliant or no continuous violations exceed 5 seconds.
                    </p>
                  </div>
                )}
              </div>
            </div>
          </SectionCard>

          {/* Card 3: Notification Delivery Audit Log */}
          <SectionCard
            title="Notification Delivery Audit History"
            subtitle="Immutable audit log of all First Alerts, recurring reminders, and test transmissions."
          >
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div className="text-xs text-slate-600">
                  Showing latest <span className="font-bold text-slate-900">{emailHistory.length}</span> notification records.
                </div>
                <button
                  type="button"
                  onClick={handleRefreshEmailHistory}
                  disabled={isLoadingEmailHistory}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 shadow-2xs hover:bg-slate-50 disabled:opacity-50"
                >
                  <RefreshCw className={`h-3.5 w-3.5 ${isLoadingEmailHistory ? 'animate-spin' : ''}`} />
                  Refresh Log
                </button>
              </div>

              {emailHistory.length > 0 ? (
                <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-slate-50 text-slate-600 border-b border-slate-200">
                      <tr>
                        <th className="px-4 py-3 font-semibold">Date & Time</th>
                        <th className="px-4 py-3 font-semibold">Alert Type</th>
                        <th className="px-4 py-3 font-semibold">Incident</th>
                        <th className="px-4 py-3 font-semibold">Worker</th>
                        <th className="px-4 py-3 font-semibold">Violation</th>
                        <th className="px-4 py-3 font-semibold">Recipient</th>
                        <th className="px-4 py-3 font-semibold">Status</th>
                        <th className="px-4 py-3 font-semibold">Delivery Notes</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {emailHistory.map((item) => (
                        <tr key={item.id} className="hover:bg-slate-50/70">
                          <td className="px-4 py-2.5 text-slate-600 font-mono text-[11px] whitespace-nowrap">
                            {item.datetime}
                          </td>
                          <td className="px-4 py-2.5">
                            <span
                              className={`inline-block px-2 py-0.5 rounded text-[10px] font-bold ${
                                item.email_type === 'First Alert'
                                  ? 'bg-rose-100 text-rose-800'
                                  : item.email_type === 'Reminder Alert'
                                  ? 'bg-orange-100 text-orange-800'
                                  : 'bg-blue-100 text-blue-800'
                              }`}
                            >
                              {item.email_type} {item.reminder_number > 0 ? `#${item.reminder_number}` : ''}
                            </span>
                          </td>
                          <td className="px-4 py-2.5 font-mono font-semibold text-slate-800">
                            {item.incident_id}
                          </td>
                          <td className="px-4 py-2.5 font-medium text-slate-700">
                            {item.worker_id ? `Worker #${item.worker_id}` : 'General / Test'}
                          </td>
                          <td className="px-4 py-2.5 font-medium text-slate-800 capitalize">
                            {item.violation_type.replace('_', ' ')}
                          </td>
                          <td className="px-4 py-2.5 font-mono text-[11px] text-slate-600">
                            {item.recipient}
                          </td>
                          <td className="px-4 py-2.5">
                            <span
                              className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold ${
                                item.status === 'delivered'
                                  ? 'bg-emerald-100 text-emerald-800'
                                  : 'bg-rose-100 text-rose-800'
                              }`}
                            >
                              {item.status === 'delivered' ? (
                                <CheckCircle2 className="h-3 w-3 text-emerald-600" />
                              ) : (
                                <AlertTriangle className="h-3 w-3 text-rose-600" />
                              )}
                              {item.status.toUpperCase()}
                            </span>
                          </td>
                          <td className="px-4 py-2.5 text-[11px] text-slate-500 max-w-xs truncate">
                            {item.status === 'delivered' ? 'Delivered successfully' : 'Delivery unsuccessful'}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="rounded-xl border border-dashed border-slate-200 bg-slate-50/50 p-6 text-center text-xs text-slate-500">
                  No email notifications logged yet. Dispatched alerts and reminders will appear here in real time.
                </div>
              )}
            </div>
          </SectionCard>
        </div>
      )}

      {/* =========================================================================
          SECTION 5: SYSTEM HEALTH AND PERFORMANCE
          ========================================================================= */}
      {activeTab === 'health' && (
        <div className="space-y-6">
          <SectionCard
            title="Real-Time System Health & Hardware Diagnostics"
            subtitle="Live hardware metrics, CPU/RAM utilization, pipeline latency, and frame rate visualizations."
          >
            <div className="space-y-6">
              {/* Top Health Metric Cards */}
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
                {/* CPU Metric Card */}
                <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-2xs space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold text-slate-500">Host CPU Utilization</span>
                    <span
                      className={`text-xs font-bold px-2 py-0.5 rounded-md ${
                        (metrics?.cpu.percent ?? 0) > 85
                          ? 'bg-rose-100 text-rose-700'
                          : 'bg-emerald-100 text-emerald-700'
                      }`}
                    >
                      {metrics?.cpu.percent ?? 0}%
                    </span>
                  </div>
                  <p className="text-2xl font-black text-slate-900">{metrics?.cpu.percent ?? 0}%</p>
                  <div className="text-[11px] text-slate-500 flex justify-between pt-1 border-t border-slate-100">
                    <span>{metrics?.cpu.physical_cores ?? 0} Cores ({metrics?.cpu.logical_cores ?? 0} Logical)</span>
                    <span>{metrics?.cpu.frequency_mhz ?? 0} MHz</span>
                  </div>
                </div>

                {/* RAM Metric Card */}
                <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-2xs space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold text-slate-500">Memory Utilization</span>
                    <span
                      className={`text-xs font-bold px-2 py-0.5 rounded-md ${
                        (metrics?.ram.percent ?? 0) > 85
                          ? 'bg-rose-100 text-rose-700'
                          : 'bg-blue-100 text-blue-700'
                      }`}
                    >
                      {metrics?.ram.percent ?? 0}%
                    </span>
                  </div>
                  <p className="text-2xl font-black text-slate-900">
                    {metrics?.ram.used_gb ?? 0} / {metrics?.ram.total_gb ?? 0} GB
                  </p>
                  <div className="text-[11px] text-slate-500 flex justify-between pt-1 border-t border-slate-100">
                    <span>Process RSS: {metrics?.ram.backend_process_rss_mb ?? 0} MB</span>
                    <span>Free: {metrics?.ram.free_gb ?? 0} GB</span>
                  </div>
                </div>

                {/* GPU Metric Card */}
                <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-2xs space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold text-slate-500">GPU Device</span>
                    <StatusPill tone={metrics?.gpu.available ? 'green' : 'slate'}>
                      {metrics?.gpu.available ? 'Active' : 'N/A'}
                    </StatusPill>
                  </div>
                  <p className="text-sm font-bold text-slate-900 truncate">
                    {metrics?.gpu.name ?? 'N/A'}
                  </p>
                  <div className="text-[11px] text-slate-500 pt-1 border-t border-slate-100">
                    <span>{metrics?.gpu.status ?? 'N/A (CPU Inference Execution)'}</span>
                  </div>
                </div>

                {/* AI Pipeline Health */}
                <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-2xs space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold text-slate-500">Pipeline Performance</span>
                    <StatusPill
                      tone={
                        metrics?.performance_status === 'Normal'
                          ? 'green'
                          : metrics?.performance_status === 'Moderate'
                          ? 'amber'
                          : 'red'
                      }
                    >
                      {metrics?.performance_status ?? 'Normal'}
                    </StatusPill>
                  </div>
                  <p className="text-2xl font-black text-slate-900">
                    {metrics?.ai_pipeline.latest_inference_latency_ms ?? 0} ms
                  </p>
                  <div className="text-[11px] text-slate-500 flex justify-between pt-1 border-t border-slate-100">
                    <span>Avg: {metrics?.ai_pipeline.avg_inference_latency_ms ?? 0} ms</span>
                    <span>FPS: {metrics?.ai_pipeline.fps ?? 0}</span>
                  </div>
                </div>
              </div>

              {/* Bounded Historical Charts using Recharts */}
              <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
                {/* Chart 1: CPU & RAM Utilization History */}
                <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-2xs space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-slate-900">Hardware Utilization History</span>
                    <div className="flex items-center gap-3 text-[11px]">
                      <span className="flex items-center gap-1 font-medium text-brand-600">
                        <span className="h-2 w-2 rounded-full bg-brand-500"></span> CPU %
                      </span>
                      <span className="flex items-center gap-1 font-medium text-emerald-600">
                        <span className="h-2 w-2 rounded-full bg-emerald-500"></span> RAM %
                      </span>
                    </div>
                  </div>

                  <div className="h-56 w-full">
                    {metricsHistory.length > 0 ? (
                      <ResponsiveContainer width="100%" height="100%">
                        <AreaChart data={metricsHistory} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                          <defs>
                            <linearGradient id="cpuGrad" x1="0" y1="0" x2="0" y2="1">
                              <stop offset="5%" stopColor="#4f46e5" stopOpacity={0.4} />
                              <stop offset="95%" stopColor="#4f46e5" stopOpacity={0.0} />
                            </linearGradient>
                            <linearGradient id="ramGrad" x1="0" y1="0" x2="0" y2="1">
                              <stop offset="5%" stopColor="#10b981" stopOpacity={0.4} />
                              <stop offset="95%" stopColor="#10b981" stopOpacity={0.0} />
                            </linearGradient>
                          </defs>
                          <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                          <XAxis dataKey="time" tick={{ fontSize: 10, fill: '#94a3b8' }} />
                          <YAxis domain={[0, 100]} tick={{ fontSize: 10, fill: '#94a3b8' }} />
                          <Tooltip contentStyle={{ fontSize: 11, borderRadius: 8 }} />
                          <Area type="monotone" dataKey="cpu" stroke="#4f46e5" fillOpacity={1} fill="url(#cpuGrad)" />
                          <Area type="monotone" dataKey="ram" stroke="#10b981" fillOpacity={1} fill="url(#ramGrad)" />
                        </AreaChart>
                      </ResponsiveContainer>
                    ) : (
                      <div className="flex h-full items-center justify-center text-xs text-slate-400">
                        Collecting diagnostic metrics...
                      </div>
                    )}
                  </div>
                </div>

                {/* Chart 2: AI Inference Latency & FPS History */}
                <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-2xs space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-slate-900">Inference Latency & FPS History</span>
                    <div className="flex items-center gap-3 text-[11px]">
                      <span className="flex items-center gap-1 font-medium text-amber-600">
                        <span className="h-2 w-2 rounded-full bg-amber-500"></span> Latency (ms)
                      </span>
                      <span className="flex items-center gap-1 font-medium text-sky-600">
                        <span className="h-2 w-2 rounded-full bg-sky-500"></span> FPS
                      </span>
                    </div>
                  </div>

                  <div className="h-56 w-full">
                    {metricsHistory.length > 0 ? (
                      <ResponsiveContainer width="100%" height="100%">
                        <LineChart data={metricsHistory} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                          <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                          <XAxis dataKey="time" tick={{ fontSize: 10, fill: '#94a3b8' }} />
                          <YAxis tick={{ fontSize: 10, fill: '#94a3b8' }} />
                          <Tooltip contentStyle={{ fontSize: 11, borderRadius: 8 }} />
                          <Line type="monotone" dataKey="latency" stroke="#f59e0b" strokeWidth={2} dot={false} />
                          <Line type="monotone" dataKey="fps" stroke="#0284c7" strokeWidth={2} dot={false} />
                        </LineChart>
                      </ResponsiveContainer>
                    ) : (
                      <div className="flex h-full items-center justify-center text-xs text-slate-400">
                        Awaiting video pipeline execution...
                      </div>
                    )}
                  </div>
                </div>
              </div>

              {/* Real-time Diagnostics Table */}
              <div className="rounded-xl border border-slate-200 bg-slate-50/50 p-4 text-xs space-y-2">
                <span className="font-semibold text-slate-700 block">AI Engine Diagnostics:</span>
                <div className="grid grid-cols-2 gap-4 sm:grid-cols-4 text-xs">
                  <div>
                    <span className="text-slate-500 block">Model Init Time:</span>
                    <span className="font-bold text-slate-900">{metrics?.ai_pipeline.model_init_ms ?? 0} ms</span>
                  </div>
                  <div>
                    <span className="text-slate-500 block">Peak Inference Latency:</span>
                    <span className="font-bold text-slate-900">{metrics?.ai_pipeline.max_inference_latency_ms ?? 0} ms</span>
                  </div>
                  <div>
                    <span className="text-slate-500 block">Total Detections Evaluated:</span>
                    <span className="font-bold text-slate-900">{metrics?.ai_pipeline.total_detections ?? 0}</span>
                  </div>
                  <div>
                    <span className="text-slate-500 block">Camera Video Stream:</span>
                    <span className="font-bold text-slate-900">
                      {metrics?.camera.is_running ? 'Streaming Active' : 'Idle'}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </SectionCard>
        </div>
      )}

      {/* =========================================================================
          SECTION 6: STORAGE AND EVIDENCE MANAGEMENT
          ========================================================================= */}
      {activeTab === 'storage' && settings && (
        <div className="space-y-6">
          <SectionCard
            title="Storage & Incident Evidence Management"
            subtitle="Manage evidence image retention policies, local disk footprint, and automatic storage purging."
          >
            <div className="space-y-6">
              {/* Storage KPI Cards */}
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
                <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-2xs space-y-1">
                  <span className="text-xs font-semibold text-slate-500">Incident Evidence Files</span>
                  <p className="text-2xl font-black text-slate-900">
                    {metrics?.storage.image_files ?? 0} Images
                  </p>
                  <p className="text-[11px] text-slate-500">
                    {metrics?.storage.incident_records_count ?? 0} total metadata records
                  </p>
                </div>

                <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-2xs space-y-1">
                  <span className="text-xs font-semibold text-slate-500">Evidence Disk Usage</span>
                  <p className="text-2xl font-black text-slate-900">
                    {metrics?.storage.total_size_mb ?? 0} MB
                  </p>
                  <p className="text-[11px] text-slate-500">
                    Directory: <code className="text-[10px] bg-slate-100 px-1 py-0.5 rounded">backend/storage/evidence</code>
                  </p>
                </div>

                <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-2xs space-y-1">
                  <span className="text-xs font-semibold text-slate-500">Host Free Storage</span>
                  <p className="text-2xl font-black text-slate-900">
                    {metrics?.storage.disk_free_gb ?? 0} GB Free
                  </p>
                  <p className="text-[11px] text-slate-500">
                    of {metrics?.storage.disk_total_gb ?? 0} GB volume capacity
                  </p>
                </div>
              </div>

              {/* Storage Retention Settings */}
              <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
                <div className="space-y-2 p-4 rounded-xl border border-slate-200 bg-slate-50/40">
                  <label className="block text-xs font-bold text-slate-900 mb-1">
                    Evidence Retention Period
                  </label>
                  <select
                    value={settings.storage.retention_days}
                    onChange={(e) =>
                      updateSettingsField('storage', 'retention_days', parseInt(e.target.value, 10))
                    }
                    className="w-full rounded-xl border border-slate-300 bg-white px-3.5 py-2.5 text-xs font-semibold text-slate-900 shadow-2xs transition focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20"
                  >
                    <option value={7}>7 Days Retention</option>
                    <option value={14}>14 Days Retention</option>
                    <option value={30}>30 Days Retention (Standard Industrial)</option>
                    <option value={60}>60 Days Retention</option>
                    <option value={90}>90 Days Retention (OSHA Audit Standard)</option>
                    <option value={180}>180 Days Retention</option>
                    <option value={365}>365 Days Retention (1 Year)</option>
                    <option value={0}>Indefinite (Never Auto-Purge)</option>
                  </select>
                  <p className="text-[11px] text-slate-500">
                    Evidence frames older than this threshold can be safely cleared to reclaim disk space.
                  </p>
                </div>

                <div className="flex items-center justify-between p-4 rounded-xl border border-slate-200 bg-white shadow-2xs">
                  <div className="space-y-0.5">
                    <span className="text-xs font-bold text-slate-900">Annotated Frame Capture</span>
                    <p className="text-[11px] text-slate-500">Save visual JPEG incident frames when violations are confirmed.</p>
                  </div>
                  <label className="relative inline-flex items-center cursor-pointer">
                    <input
                      type="checkbox"
                      checked={settings.storage.image_capture_enabled}
                      onChange={(e) =>
                        updateSettingsField('storage', 'image_capture_enabled', e.target.checked)
                      }
                      className="sr-only peer"
                    />
                    <div className="w-10 h-6 bg-slate-200 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-brand-600"></div>
                  </label>
                </div>
              </div>

              {/* Purge Button */}
              <div className="pt-2">
                <button
                  type="button"
                  onClick={() => setShowCleanupModal(true)}
                  disabled={isCleaningStorage}
                  className="inline-flex items-center gap-2 rounded-xl border border-rose-200 bg-rose-50 px-4 py-2.5 text-xs font-semibold text-rose-700 shadow-2xs transition hover:bg-rose-100 disabled:opacity-50"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                  {isCleaningStorage ? 'Purging Evidence...' : 'Clear Expired Evidence Now'}
                </button>
              </div>
            </div>
          </SectionCard>
        </div>
      )}

      {/* =========================================================================
          SECTION 7: APPLICATION PREFERENCES
          ========================================================================= */}
      {activeTab === 'preferences' && settings && (
        <div className="space-y-6">
          <SectionCard
            title="Application & Interface Preferences"
            subtitle="Customize interface themes, default landing views, refresh frequencies, and notification display styles."
          >
            <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3">
              {/* Theme Preference */}
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                  Theme Appearance
                </label>
                <select
                  value={settings.preferences.theme}
                  onChange={(e) =>
                    updateSettingsField(
                      'preferences',
                      'theme',
                      e.target.value as 'light' | 'dark' | 'system'
                    )
                  }
                  className="w-full rounded-xl border border-slate-300 bg-white px-3.5 py-2.5 text-xs font-semibold text-slate-900 shadow-2xs transition focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20"
                >
                  <option value="light">Light Glassmorphism (Default)</option>
                  <option value="dark">Dark Industrial</option>
                  <option value="system">System Synchronized</option>
                </select>
              </div>

              {/* Default Landing Page */}
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                  Default Landing Page
                </label>
                <select
                  value={settings.preferences.default_page}
                  onChange={(e) =>
                    updateSettingsField('preferences', 'default_page', e.target.value)
                  }
                  className="w-full rounded-xl border border-slate-300 bg-white px-3.5 py-2.5 text-xs font-semibold text-slate-900 shadow-2xs transition focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20"
                >
                  <option value="dashboard">Overview / Executive Dashboard</option>
                  <option value="monitoring">Live Camera Monitoring Feed</option>
                  <option value="workers">Worker Safety Profiles</option>
                  <option value="reports">Compliance & Incident Reports</option>
                </select>
              </div>

              {/* Refresh Interval */}
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                  Dashboard Auto-Refresh Interval
                </label>
                <select
                  value={settings.preferences.refresh_interval_ms}
                  onChange={(e) =>
                    updateSettingsField(
                      'preferences',
                      'refresh_interval_ms',
                      parseInt(e.target.value, 10)
                    )
                  }
                  className="w-full rounded-xl border border-slate-300 bg-white px-3.5 py-2.5 text-xs font-semibold text-slate-900 shadow-2xs transition focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20"
                >
                  <option value={1000}>1 Second (High Responsiveness)</option>
                  <option value={2000}>2 Seconds (Balanced)</option>
                  <option value={5000}>5 Seconds (Low Bandwidth)</option>
                  <option value={10000}>10 Seconds (Power Saver)</option>
                </select>
              </div>

              {/* Notification Display Mode */}
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                  Notification Display Mode
                </label>
                <select
                  value={settings.preferences.notification_mode}
                  onChange={(e) =>
                    updateSettingsField('preferences', 'notification_mode', e.target.value)
                  }
                  className="w-full rounded-xl border border-slate-300 bg-white px-3.5 py-2.5 text-xs font-semibold text-slate-900 shadow-2xs transition focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20"
                >
                  <option value="banner">Prominent Glass Banner</option>
                  <option value="toast">Subtle Corner Toast</option>
                  <option value="minimal">Minimal Status Bar Only</option>
                </select>
              </div>

              {/* Datetime Format */}
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                  Timestamp Display Format
                </label>
                <select
                  value={settings.preferences.datetime_format}
                  onChange={(e) =>
                    updateSettingsField('preferences', 'datetime_format', e.target.value)
                  }
                  className="w-full rounded-xl border border-slate-300 bg-white px-3.5 py-2.5 text-xs font-semibold text-slate-900 shadow-2xs transition focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20"
                >
                  <option value="24h">24-Hour Industrial (14:30:00)</option>
                  <option value="12h">12-Hour AM/PM (02:30:00 PM)</option>
                </select>
              </div>

              {/* UI Density */}
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                  UI Table & Layout Density
                </label>
                <select
                  value={settings.preferences.ui_density}
                  onChange={(e) =>
                    updateSettingsField('preferences', 'ui_density', e.target.value)
                  }
                  className="w-full rounded-xl border border-slate-300 bg-white px-3.5 py-2.5 text-xs font-semibold text-slate-900 shadow-2xs transition focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20"
                >
                  <option value="normal">Normal (Balanced Spacing)</option>
                  <option value="compact">Compact (High Information Density)</option>
                </select>
              </div>
            </div>
          </SectionCard>
        </div>
      )}

      {/* =========================================================================
          SECTION 8: SYSTEM INFORMATION
          ========================================================================= */}
      {activeTab === 'info' && (
        <div className="space-y-6">
          <SectionCard
            title="System Architecture & Service Registry"
            subtitle="Runtime environment, system uptime, and operational health of all backend monitoring engines."
          >
            <div className="space-y-6">
              {/* Architecture Metadata Table */}
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4 text-xs">
                <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-2xs">
                  <span className="text-slate-500 block">Application Platform</span>
                  <p className="text-sm font-bold text-slate-900 mt-1">
                    {systemInfo?.application_name ?? 'SafeVision AI'} v{systemInfo?.version ?? '1.0.0'}
                  </p>
                  <p className="text-[11px] text-slate-500 mt-0.5">{systemInfo?.environment ?? 'Local Industrial Edge'}</p>
                </div>

                <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-2xs">
                  <span className="text-slate-500 block">Operating System</span>
                  <p className="text-sm font-bold text-slate-900 mt-1 truncate">
                    {systemInfo?.os_platform ?? 'Windows 10/11 (AMD64)'}
                  </p>
                  <p className="text-[11px] text-slate-500 mt-0.5">
                    {systemInfo?.cpu_cores.physical ?? 0} physical / {systemInfo?.cpu_cores.logical ?? 0} logical cores
                  </p>
                </div>

                <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-2xs">
                  <span className="text-slate-500 block">Runtime Environment</span>
                  <p className="text-sm font-bold text-slate-900 mt-1">
                    Python {systemInfo?.python_version ?? '3.12'}
                  </p>
                  <p className="text-[11px] text-slate-500 mt-0.5">
                    PyTorch {systemInfo?.pytorch_version ?? '2.x'}
                  </p>
                </div>

                <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-2xs">
                  <span className="text-slate-500 block">System Uptime</span>
                  <p className="text-sm font-bold text-slate-900 mt-1 flex items-center gap-1.5">
                    <Clock className="h-3.5 w-3.5 text-brand-600" />
                    {systemInfo
                      ? `${Math.floor(systemInfo.system_uptime_seconds / 3600)}h ${Math.floor(
                          (systemInfo.system_uptime_seconds % 3600) / 60
                        )}m`
                      : 'Active'}
                  </p>
                  <p className="text-[11px] text-slate-500 mt-0.5">Continuous Monitoring Ready</p>
                </div>
              </div>

              {/* Service Registry Status Cards */}
              <div className="space-y-3">
                <span className="text-xs font-bold text-slate-900 block">Active Micro-Service Registry:</span>
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
                  {systemInfo?.services.map((svc) => (
                    <div
                      key={svc.name}
                      className="flex items-start justify-between p-3.5 rounded-xl border border-slate-200 bg-white text-xs shadow-2xs"
                    >
                      <div className="space-y-0.5">
                        <span className="font-bold text-slate-900 block">{svc.name}</span>
                        <p className="text-[11px] text-slate-500">{svc.description}</p>
                      </div>
                      <StatusPill tone="green">Operational</StatusPill>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </SectionCard>
        </div>
      )}

      {/* Confirmation Modal: Reset to Defaults */}
      {showResetModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-xs p-4">
          <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-xl space-y-4 border border-slate-200">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-rose-100 text-rose-600">
                <RotateCcw className="h-5 w-5" />
              </div>
              <div>
                <h3 className="text-base font-bold text-slate-900">Reset System Settings?</h3>
                <p className="text-xs text-slate-500">Restore factory defaults across all 8 modules.</p>
              </div>
            </div>

            <p className="text-xs text-slate-600 leading-relaxed">
              This will reset camera parameters, PPE confidence thresholds, alarm frequencies, and application preferences back to the factory baseline. This action takes effect immediately.
            </p>

            <div className="flex justify-end gap-2.5 pt-2">
              <button
                type="button"
                onClick={() => setShowResetModal(false)}
                className="rounded-xl border border-slate-200 bg-white px-4 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleResetDefaults}
                className="rounded-xl bg-rose-600 px-4 py-2 text-xs font-semibold text-white shadow-xs hover:bg-rose-700"
              >
                Yes, Reset All Settings
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Confirmation Modal: Clear Expired Evidence */}
      {showCleanupModal && settings && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-xs p-4">
          <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-xl space-y-4 border border-slate-200">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-rose-100 text-rose-600">
                <Trash2 className="h-5 w-5" />
              </div>
              <div>
                <h3 className="text-base font-bold text-slate-900">Purge Expired Incident Evidence?</h3>
                <p className="text-xs text-slate-500">
                  Delete files older than {settings.storage.retention_days} days.
                </p>
              </div>
            </div>

            <p className="text-xs text-slate-600 leading-relaxed">
              All annotated JPEG frames and metadata records created more than {settings.storage.retention_days} days ago will be permanently removed from disk.
            </p>

            <div className="flex justify-end gap-2.5 pt-2">
              <button
                type="button"
                onClick={() => setShowCleanupModal(false)}
                className="rounded-xl border border-slate-200 bg-white px-4 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleCleanupEvidence}
                className="rounded-xl bg-rose-600 px-4 py-2 text-xs font-semibold text-white shadow-xs hover:bg-rose-700"
              >
                Confirm & Purge Files
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Confirmation Modal: Send Test Email */}
      {testRecipientModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-xs p-4">
          <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-xl space-y-4 border border-slate-200">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-brand-50 text-brand-600 border border-brand-200">
                <Mail className="h-5 w-5" />
              </div>
              <div>
                <h3 className="text-base font-bold text-slate-900">Send Test Email Alert</h3>
                <p className="text-xs text-slate-500">
                  Verify SMTP delivery and recipient inbox reachability.
                </p>
              </div>
            </div>

            <div className="space-y-1.5 pt-1">
              <label className="text-xs font-bold text-slate-700">Target Recipient Address</label>
              <input
                type="email"
                value={customTestEmail}
                onChange={(e) => setCustomTestEmail(e.target.value)}
                placeholder="bhavaneshkadiveti@gmail.com"
                className="w-full rounded-xl border border-slate-200 bg-white px-3.5 py-2.5 text-xs font-medium text-slate-900 shadow-2xs focus:border-brand-500 focus:outline-hidden"
              />
              <p className="text-[11px] text-slate-500">
                A verified test alert message will be sent to this address immediately.
              </p>
            </div>

            <div className="flex justify-end gap-2.5 pt-2">
              <button
                type="button"
                onClick={() => setTestRecipientModal(false)}
                className="rounded-xl border border-slate-200 bg-white px-4 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={() => handleSendTestEmail(customTestEmail)}
                disabled={isSendingTestEmail || !isValidEmailAddress(customTestEmail)}
                className="inline-flex items-center gap-2 rounded-xl bg-brand-600 px-4 py-2 text-xs font-semibold text-white shadow-xs hover:bg-brand-700 disabled:opacity-50"
              >
                <Send className={`h-3.5 w-3.5 ${isSendingTestEmail ? 'animate-spin' : ''}`} />
                {isSendingTestEmail ? 'Sending...' : 'Send Test Alert'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
