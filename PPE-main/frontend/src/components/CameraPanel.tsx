import React, { useState, useEffect, useRef } from 'react';
import {
  Button,
  MenuItem,
  Select,
  FormControl,
  InputLabel,
  CircularProgress,
  Alert,
} from '@mui/material';
import { VideoOff, Play, Square, RotateCcw, AlertTriangle } from 'lucide-react';
import SectionCard from '@/components/SectionCard';
import { API_BASE_URL } from '@/services/api';

interface CameraPanelProps {
  isRunning: boolean;
  isStarting: boolean;
  isStopping: boolean;
  cameraIndex: number;
  currentFps: number;
  resolution: string;
  onStart: (cameraIndex: number) => Promise<boolean>;
  onStop: () => Promise<boolean>;
  error?: string | null;
  onClearError?: () => void;
}

export const CameraPanel: React.FC<CameraPanelProps> = React.memo(({
  isRunning,
  isStarting,
  isStopping,
  cameraIndex: initialCameraIndex,
  currentFps,
  resolution,
  onStart,
  onStop,
  error,
  onClearError,
}) => {
  const [selectedCamera, setSelectedCamera] = useState<number>(initialCameraIndex || 0);
  const [streamKey, setStreamKey] = useState<number>(0);
  const [hasLoadedFrame, setHasLoadedFrame] = useState<boolean>(false);
  const [streamError, setStreamError] = useState<string | null>(null);

  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // When monitoring state stops, reset frame and timer state
  useEffect(() => {
    if (!isRunning) {
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
    }
  }, [isRunning]);

  // Clean up timer on unmount
  useEffect(() => {
    return () => {
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
      }
    };
  }, []);

  const handleStart = async () => {
    setStreamError(null);
    setHasLoadedFrame(false);
    setStreamKey((k) => k + 1);
    await onStart(selectedCamera);
  };

  const handleStop = async () => {
    setHasLoadedFrame(false);
    setStreamError(null);
    await onStop();
  };

  const handleManualStreamRetry = () => {
    setStreamError(null);
    setHasLoadedFrame(false);
    setStreamKey((k) => k + 1);
  };

  const videoFeedUrl = `${API_BASE_URL}/api/monitoring/video_feed?t=${streamKey}`;

  return (
    <SectionCard
      title="Live Camera Monitoring"
      subtitle={
        isRunning
          ? `Hardware Camera #${selectedCamera} active · Real-time inference`
          : 'Webcam hardware idle'
      }
    >
      {/* Error Banner */}
      {error && (
        <div className="mb-3">
          <Alert
            severity="error"
            onClose={onClearError}
            className="rounded-xl border border-rose-200 text-xs"
          >
            {error}
          </Alert>
        </div>
      )}

      {/* Video Preview Viewport */}
      <div className="relative aspect-video w-full overflow-hidden rounded-xl border border-slate-200 bg-slate-950 text-white shadow-inner">
        {isRunning ? (
          <>
            {/* Live MJPEG Image Stream from Backend */}
            <img
              src={videoFeedUrl}
              alt="Live annotated camera preview"
              className="h-full w-full object-contain"
              onLoad={() => {
                setHasLoadedFrame(true);
                setStreamError(null);
              }}
              onError={() => {
                if (isRunning) {
                  setStreamError('Waiting for annotated frames from camera feed...');
                  // Automatically retry after 2 seconds
                  if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
                  reconnectTimerRef.current = setTimeout(() => {
                    if (isRunning) {
                      setStreamKey(Date.now());
                    }
                  }, 2000);
                }
              }}
            />

            {/* Loading Overlay before first frame arrives */}
            {!hasLoadedFrame && !streamError && (
              <div className="absolute inset-0 flex flex-col items-center justify-center bg-slate-950/80 backdrop-blur-xs p-4 text-center">
                <CircularProgress size={36} className="text-brand-400" />
                <p className="mt-3 text-xs font-semibold text-slate-200">
                  Connecting to live webcam feed...
                </p>
                <p className="mt-1 text-[11px] text-slate-400">
                  Initializing camera hardware #{selectedCamera} and detection pipeline.
                </p>
              </div>
            )}

            {/* Error Overlay with Reconnect Action */}
            {streamError && !hasLoadedFrame && (
              <div className="absolute inset-0 flex flex-col items-center justify-center bg-slate-950/90 p-4 text-center">
                <AlertTriangle className="h-8 w-8 text-amber-400 animate-pulse" />
                <p className="mt-2 text-xs font-semibold text-amber-200">{streamError}</p>
                <p className="mt-1 max-w-xs text-[11px] text-slate-400">
                  The backend capture loop is warming up or reconnecting. Retrying automatically...
                </p>
                <button
                  type="button"
                  onClick={handleManualStreamRetry}
                  className="mt-3 inline-flex items-center gap-1.5 rounded-lg border border-amber-400/30 bg-amber-500/20 px-3 py-1.5 text-xs font-semibold text-amber-200 hover:bg-amber-500/30 transition"
                >
                  <RotateCcw className="h-3.5 w-3.5" />
                  Retry Stream Now
                </button>
              </div>
            )}
          </>
        ) : (
          /* Idle State */
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 text-slate-400">
            <VideoOff className="h-10 w-10 text-slate-600" />
            <span className="inline-flex items-center gap-2 rounded-full border border-slate-700 bg-slate-800/80 px-3 py-1 text-xs font-semibold text-slate-300">
              <span className="h-2 w-2 rounded-full bg-slate-500" />
              Camera: Not Connected (Idle)
            </span>
            <p className="mt-1 text-xs text-slate-500">
              Select a hardware index and click Start Monitoring to initiate live video feed.
            </p>
          </div>
        )}

        {/* Real-time telemetry overlay indicators */}
        <div className="absolute bottom-2.5 left-2.5 flex flex-wrap gap-2 pointer-events-none">
          <span className="rounded-md bg-black/75 backdrop-blur-xs px-2.5 py-1 text-[11px] font-mono font-bold text-slate-200 border border-white/10">
            FPS: {isRunning ? currentFps.toFixed(1) : '0.0'}
          </span>
          <span className="rounded-md bg-black/75 backdrop-blur-xs px-2.5 py-1 text-[11px] font-mono font-medium text-slate-300 border border-white/10">
            {isRunning ? resolution : 'Idle'}
          </span>
          {isRunning && (
            <span className="rounded-md bg-emerald-600/90 backdrop-blur-xs px-2 py-1 text-[11px] font-bold text-white flex items-center gap-1 border border-emerald-400/30">
              <span className="h-1.5 w-1.5 rounded-full bg-white animate-ping" />
              LIVE STREAM
            </span>
          )}
        </div>
      </div>

      {/* Control Actions */}
      <div className="mt-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <FormControl
          size="small"
          disabled={isRunning || isStarting || isStopping}
          className="w-full sm:w-48"
        >
          <InputLabel id="camera-select-label">Camera Index</InputLabel>
          <Select
            labelId="camera-select-label"
            label="Camera Index"
            value={selectedCamera}
            onChange={(e) => setSelectedCamera(Number(e.target.value))}
          >
            <MenuItem value={0}>Camera 0 (Default)</MenuItem>
            <MenuItem value={1}>Camera 1 (Secondary)</MenuItem>
            <MenuItem value={2}>Camera 2 (External USB)</MenuItem>
          </Select>
        </FormControl>

        <div className="flex items-center gap-2.5">
          {!isRunning ? (
            <Button
              variant="contained"
              color="primary"
              onClick={handleStart}
              disabled={isStarting}
              startIcon={
                isStarting ? (
                  <CircularProgress size={16} color="inherit" />
                ) : (
                  <Play className="h-4 w-4" />
                )
              }
              className="!font-semibold !shadow-xs"
            >
              {isStarting ? 'Starting Camera...' : 'Start Monitoring'}
            </Button>
          ) : (
            <Button
              variant="contained"
              color="error"
              onClick={handleStop}
              disabled={isStopping}
              startIcon={
                isStopping ? (
                  <CircularProgress size={16} color="inherit" />
                ) : (
                  <Square className="h-4 w-4" />
                )
              }
              className="!font-semibold !shadow-xs"
            >
              {isStopping ? 'Stopping Worker...' : 'Stop Monitoring'}
            </Button>
          )}
        </div>
      </div>
    </SectionCard>
  );
});

export default CameraPanel;
