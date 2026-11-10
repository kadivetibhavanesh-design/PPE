import React, { Suspense, lazy } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { ThemeProvider, CssBaseline } from '@mui/material';
import { theme } from './theme';
import DashboardLayout from '@/layouts/DashboardLayout';

// Lazy-loaded route components for optimal initial bundle size and fast TTI
const OverviewPage = lazy(() => import('@/pages/OverviewPage'));
const LiveMonitoringPage = lazy(() => import('@/pages/LiveMonitoringPage'));
const WorkersPage = lazy(() => import('@/pages/WorkersPage'));
const PPECompliancePage = lazy(() => import('@/pages/PPECompliancePage'));
const ViolationsPage = lazy(() => import('@/pages/ViolationsPage'));
const IncidentHistoryPage = lazy(() => import('@/pages/IncidentHistoryPage'));
const ReportsPage = lazy(() => import('@/pages/ReportsPage'));
const SettingsPage = lazy(() => import('@/pages/SettingsPage'));
const NotificationsPage = lazy(() => import('@/pages/NotificationsPage'));

const PageFallback: React.FC = () => (
  <div className="flex h-96 w-full items-center justify-center">
    <div className="flex flex-col items-center gap-3">
      <div className="h-8 w-8 animate-spin rounded-full border-3 border-brand-600 border-t-transparent" />
      <span className="text-xs font-semibold text-slate-500">Loading module...</span>
    </div>
  </div>
);

export const AppRoutes: React.FC = () => (
  <Suspense fallback={<PageFallback />}>
    <Routes>
      <Route element={<DashboardLayout />}>
        <Route index element={<OverviewPage />} />
        <Route path="live-monitoring" element={<LiveMonitoringPage />} />
        <Route path="workers" element={<WorkersPage />} />
        <Route path="ppe-compliance" element={<PPECompliancePage />} />
        <Route path="violations" element={<ViolationsPage />} />
        <Route path="incident-history" element={<IncidentHistoryPage />} />
        <Route path="reports" element={<ReportsPage />} />
        <Route path="settings" element={<SettingsPage />} />
        <Route path="notifications" element={<NotificationsPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  </Suspense>
);

export const App: React.FC = () => (
  <ThemeProvider theme={theme}>
    <CssBaseline />
    <BrowserRouter>
      <AppRoutes />
    </BrowserRouter>
  </ThemeProvider>
);

export default App;
