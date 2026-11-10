import { useState } from 'react';
import CameraPanel from '@/components/CameraPanel';
import DetectionOverlayPreview from '@/components/DetectionOverlayPreview';
import WorkerTrackingPanel from '@/components/WorkerTrackingPanel';
import PpeCompliancePanel from '@/components/PpeCompliancePanel';
import DetectionEventsTable from '@/components/DetectionEventsTable';
import { useLiveMonitoring } from '@/hooks/useLiveMonitoring';

export default function LiveMonitoringPage() {
  const {
    status,
    isStarting,
    isStopping,
    latestSnapshot,
    workers,
    activeViolations,
    violationTimers,
    error,
    startMonitoring,
    stopMonitoring,
    clearError,
  } = useLiveMonitoring();

  const [selectedWorkerId, setSelectedWorkerId] = useState<number | null>(null);

  const isRunning = status?.is_running ?? false;
  const isStartingCombined = isStarting || status?.status === 'starting';
  const isStoppingCombined = isStopping || status?.status === 'stopping';
  const currentFps = status?.current_fps ?? 0;
  const frameWidth = latestSnapshot?.frame_width ?? 1280;
  const frameHeight = latestSnapshot?.frame_height ?? 720;
  const resolution = `${frameWidth} x ${frameHeight}`;

  return (
    <div className="space-y-6">
      {/* 1. Page Header */}
      <div className="glass-card rounded-2xl p-5 sm:p-6">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="space-y-1.5">
            <h2 className="text-2xl font-bold tracking-tight text-slate-900">Live Monitoring</h2>
            <p className="max-w-2xl text-sm text-slate-600">
              Real-time worker and PPE compliance monitoring.
            </p>
          </div>
        </div>
      </div>

      {/* 2. Camera Monitoring and Real-Time Detection Overlay */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <CameraPanel
          isRunning={isRunning}
          isStarting={isStartingCombined}
          isStopping={isStoppingCombined}
          cameraIndex={status?.camera_index ?? 0}
          currentFps={currentFps}
          resolution={resolution}
          onStart={startMonitoring}
          onStop={stopMonitoring}
          error={error}
          onClearError={clearError}
        />
        <DetectionOverlayPreview
          workers={workers}
          frameWidth={frameWidth}
          frameHeight={frameHeight}
          isRunning={isRunning}
        />
      </div>

      {/* 3. Worker Tracking & PPE Compliance Breakdown */}
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
        <div className="xl:col-span-2">
          <WorkerTrackingPanel
            workers={workers}
            violationTimers={violationTimers}
            isRunning={isRunning}
          />
        </div>
        <PpeCompliancePanel
          workers={workers}
          selectedWorkerId={selectedWorkerId}
          onSelectWorker={setSelectedWorkerId}
        />
      </div>

      {/* 4. Live Violation Events Audit Table */}
      <DetectionEventsTable events={activeViolations} isRunning={isRunning} />
    </div>
  );
}
