import copy
import json
import logging
import os
from pathlib import Path
import platform
import shutil
import sys
import threading
import time
from typing import Any, Dict, List, Optional, Tuple, Union
import cv2
import psutil
import torch
from dotenv import load_dotenv

# Ensure environment variables from .env are loaded
ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
for env_candidate in [ROOT_DIR / ".env", BACKEND_DIR / ".env", BACKEND_DIR.parent / ".env"]:
    if env_candidate.exists():
        load_dotenv(env_candidate, override=False)

try:
    from app.services.model_registry import (
        get_active_model_id,
        set_active_model_id,
        get_model_profile,
        list_available_models,
    )
    from app.services.model_service import get_model, get_model_init_time
    from app.services.ppe_monitoring_service import get_monitoring_service
    from app.services.monitoring_controller import get_monitoring_controller
    from app.services.evidence_service import get_evidence_service
    from app.services.alarm_service import AlarmService
    from app.services.email_service import get_email_service, is_valid_email
except ImportError:
    from backend.app.services.model_registry import (
        get_active_model_id,
        set_active_model_id,
        get_model_profile,
        list_available_models,
    )
    from backend.app.services.model_service import get_model, get_model_init_time
    from backend.app.services.ppe_monitoring_service import get_monitoring_service
    from backend.app.services.monitoring_controller import get_monitoring_controller
    from backend.app.services.evidence_service import get_evidence_service
    from backend.app.services.alarm_service import AlarmService
    from backend.app.services.email_service import get_email_service, is_valid_email

logger = logging.getLogger("ppe_monitoring.settings_service")

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
STORAGE_DIR = BACKEND_DIR / "storage"
SETTINGS_FILE = STORAGE_DIR / "settings.json"

DEFAULT_SETTINGS: Dict[str, Any] = {
    "model": {
        "selected_profile": "constructelligence",
    },
    "camera": {
        "device_index": 0,
        "resolution": "1280x720",
        "width": 1280,
        "height": 720,
        "fps": 30,
        "backend": "DirectShow" if platform.system() == "Windows" else "Default",
    },
    "ppe": {
        "global_confidence": 0.20,
        "min_ioa": 0.15,
        "violation_duration": 5.0,
        "violation_cooldown": 10.0,
        "enabled_categories": [
            "hardhat",
            "safety_vest",
            "mask",
            "gloves",
            "goggles",
        ],
        "category_confidence": {
            "hardhat": 0.20,
            "safety_vest": 0.20,
            "mask": 0.20,
            "gloves": 0.20,
            "goggles": 0.20,
        },
    },
    "alerts": {
        "sound_enabled": True,
        "visual_enabled": True,
        "duration_ms": 400,
        "frequency_hz": 1000,
        "cooldown_seconds": 10.0,
        "triggers": {
            "hardhat": True,
            "safety_vest": True,
            "mask": True,
            "gloves": True,
            "goggles": True,
        },
    },
    "storage": {
        "retention_days": 30,
        "image_capture_enabled": True,
    },
    "preferences": {
        "theme": "light",
        "default_page": "dashboard",
        "refresh_interval_ms": 2000,
        "notification_mode": "banner",
        "datetime_format": "24h",
        "ui_density": "normal",
    },
    "email": {
        "enabled": False,
        "recipient_email": "bhavaneshkadiveti@gmail.com",
        "sender_email": "",
        "smtp_host": "smtp.gmail.com",
        "smtp_port": 587,
        "smtp_username": "",
        "smtp_password": "",
        "use_tls": True,
        "use_ssl": False,
        "reminder_interval_minutes": 5,
    },
}

SANITIZED_MODEL_PROFILES = [
    {
        "profile_id": "constructelligence",
        "name": "Standard PPE Detection",
        "description": "Industrial baseline safety hazard detection. Highly optimized for high-speed tracking of core safety equipment including Hardhats, Safety Vests, Gloves, and Safety Goggles.",
        "capabilities": [
            "Real-time Person & Worker Localization",
            "Hardhat Detection (Compliant & Missing)",
            "Safety Vest Detection (Compliant & Missing)",
            "Gloves Detection (Compliant & Missing)",
            "Safety Goggles Detection (Compliant & Missing)",
            "Face Mask Verification (Missing violation detection)",
        ],
        "positive_mask_support": False,
        "positive_glove_support": True,
        "recommended_for": "Standard industrial construction sites, warehouses, and factories.",
    },
    {
        "profile_id": "vyra",
        "name": "Extended PPE Detection",
        "description": "Comprehensive multi-category safety compliance model with full dual-state verification for Face Masks and respiratory gear alongside core industrial PPE.",
        "capabilities": [
            "Real-time Person & Worker Localization",
            "Hardhat Detection (Compliant & Missing)",
            "Safety Vest Detection (Compliant & Missing)",
            "Face Mask Detection (Compliant & Missing - Full Verification)",
            "Gloves Detection (Compliant & Missing)",
            "Safety Goggles Detection (Compliant & Missing)",
        ],
        "positive_mask_support": True,
        "positive_glove_support": True,
        "recommended_for": "Healthcare facilities, chemical handling, clean rooms, and high-spec hazard zones.",
    },
]


def _deep_merge(target: Dict[str, Any], source: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively merges source dict into target dict."""
    for key, value in source.items():
        if isinstance(value, dict) and key in target and isinstance(target[key], dict):
            _deep_merge(target[key], value)
        else:
            target[key] = copy.deepcopy(value)
    return target


class SettingsService:
    """
    Centralized configuration and persistence service for SafeVision AI.
    Handles settings loading, storage, validation, device scanning, camera tests,
    and runtime synchronization across all monitoring pipeline engines.
    """

    def __init__(self, settings_path: Optional[Union[str, Path]] = None) -> None:
        self.settings_file: Path = (
            Path(settings_path).resolve() if settings_path else SETTINGS_FILE.resolve()
        )
        self._lock = threading.Lock()
        self._current_settings: Dict[str, Any] = copy.deepcopy(DEFAULT_SETTINGS)
        self._ensure_storage_dir()
        self.load_settings()

    def _ensure_storage_dir(self) -> None:
        """Ensures storage directory exists."""
        try:
            self.settings_file.parent.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.error(f"Failed to create settings directory {self.settings_file.parent}: {e}")

    def load_settings(self) -> Dict[str, Any]:
        """
        Loads configuration from disk, validating and merging with default schema.
        Creates default settings.json if missing.
        """
        with self._lock:
            merged = copy.deepcopy(DEFAULT_SETTINGS)
            if self.settings_file.exists():
                try:
                    content = self.settings_file.read_text(encoding="utf-8")
                    data = json.loads(content)
                    if isinstance(data, dict):
                        _deep_merge(merged, data)
                except Exception as e:
                    logger.warning(f"Error loading {self.settings_file}, using defaults: {e}")
            else:
                try:
                    self.settings_file.write_text(json.dumps(merged, indent=2), encoding="utf-8")
                    logger.info(f"Initialized default settings file at {self.settings_file}")
                except Exception as e:
                    logger.error(f"Failed to write default settings file: {e}")

            # Fallback to environment variables if email settings are unset
            email_cfg = merged.setdefault("email", {})
            if os.getenv("EMAIL_RECIPIENT") and not email_cfg.get("recipient_email"):
                email_cfg["recipient_email"] = os.getenv("EMAIL_RECIPIENT")
            if os.getenv("SMTP_HOST") and not email_cfg.get("smtp_host"):
                email_cfg["smtp_host"] = os.getenv("SMTP_HOST")
            if os.getenv("SMTP_PORT") and not email_cfg.get("smtp_port"):
                try:
                    email_cfg["smtp_port"] = int(os.getenv("SMTP_PORT", "587"))
                except ValueError:
                    pass
            if os.getenv("SMTP_USERNAME") and not email_cfg.get("smtp_username"):
                email_cfg["smtp_username"] = os.getenv("SMTP_USERNAME")
            if os.getenv("SMTP_PASSWORD") and not email_cfg.get("smtp_password"):
                email_cfg["smtp_password"] = os.getenv("SMTP_PASSWORD")
            if os.getenv("SMTP_SENDER_EMAIL") and not email_cfg.get("sender_email"):
                email_cfg["sender_email"] = os.getenv("SMTP_SENDER_EMAIL")
            if os.getenv("EMAIL_ENABLED") is not None:
                email_cfg["enabled"] = os.getenv("EMAIL_ENABLED", "").lower() in ("true", "1", "t")

            # Harmonize Gmail sender and username if one is missing
            host = str(email_cfg.get("smtp_host", "")).lower()
            if "gmail.com" in host or "googlemail.com" in host:
                u_name = str(email_cfg.get("smtp_username", "")).strip()
                s_email = str(email_cfg.get("sender_email", "")).strip()
                if u_name and not s_email:
                    email_cfg["sender_email"] = u_name
                elif s_email and not u_name:
                    email_cfg["smtp_username"] = s_email

            self._current_settings = merged
            return copy.deepcopy(self._current_settings)

    def get_settings(self, mask_secrets: bool = True) -> Dict[str, Any]:
        """Returns in-memory snapshot of current settings. Never leaks plaintext password when masked."""
        with self._lock:
            snapshot = copy.deepcopy(self._current_settings)
            if mask_secrets and "email" in snapshot:
                pwd = snapshot["email"].get("smtp_password", "")
                snapshot["email"]["has_password"] = bool(pwd)
                snapshot["email"]["smtp_password"] = "******" if pwd else ""
            return snapshot

    def save_settings(self, updates: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validates, updates, persists, and immediately applies settings to running engines.
        """
        with self._lock:
            # Handle email validation & password preservation before deep merge
            if "email" in updates and isinstance(updates["email"], dict):
                email_updates = dict(updates["email"])
                recip = email_updates.get("recipient_email")
                if recip is not None:
                    recip = str(recip).strip()
                    if not is_valid_email(recip):
                        raise ValueError(f"Invalid recipient email address format: '{recip}'")
                    email_updates["recipient_email"] = recip

                # Validate and harmonize Gmail SMTP sender address
                host = str(email_updates.get("smtp_host") or self._current_settings.get("email", {}).get("smtp_host", "")).lower()
                username = str(email_updates.get("smtp_username") if "smtp_username" in email_updates else self._current_settings.get("email", {}).get("smtp_username", "")).strip()
                sender = str(email_updates.get("sender_email") if "sender_email" in email_updates else self._current_settings.get("email", {}).get("sender_email", "")).strip()
                is_gmail = "gmail.com" in host or "googlemail.com" in host

                if is_gmail:
                    if username and not sender:
                        email_updates["sender_email"] = username
                    elif sender and not username:
                        email_updates["smtp_username"] = sender
                    elif username and sender and username.lower() != sender.lower():
                        raise ValueError(
                            f"For Gmail SMTP, the sender address ('{sender}') must match the authenticated SMTP username ('{username}')."
                        )

                # If incoming password is empty or masked, retain existing stored password
                existing_pwd = self._current_settings.get("email", {}).get("smtp_password", "")
                incoming_pwd = email_updates.get("smtp_password", "")
                if incoming_pwd in ("******", "", None):
                    email_updates["smtp_password"] = existing_pwd

                updates["email"] = email_updates

            _deep_merge(self._current_settings, updates)
            # Write to disk atomically
            tmp_path = self.settings_file.with_suffix(".tmp")
            try:
                tmp_path.write_text(json.dumps(self._current_settings, indent=2), encoding="utf-8")
                tmp_path.replace(self.settings_file)
                logger.info(f"Saved configuration to {self.settings_file}")
            except Exception as e:
                logger.error(f"Failed to persist settings: {e}")
                if tmp_path.exists():
                    tmp_path.unlink()

            applied = copy.deepcopy(self._current_settings)

        # Apply settings outside of file lock to prevent deadlocks
        self.apply_all(applied)
        return self.get_settings(mask_secrets=True)

    def reset_to_defaults(self) -> Dict[str, Any]:
        """Resets all configuration values to system defaults and persists."""
        with self._lock:
            self._current_settings = copy.deepcopy(DEFAULT_SETTINGS)
            try:
                self.settings_file.write_text(json.dumps(self._current_settings, indent=2), encoding="utf-8")
                logger.info("Reset settings to system defaults.")
            except Exception as e:
                logger.error(f"Failed to write defaults to settings file: {e}")
            applied = copy.deepcopy(self._current_settings)

        self.apply_all(applied)
        return applied

    def apply_all(self, settings_dict: Optional[Dict[str, Any]] = None) -> None:
        """Applies configuration across all backend services."""
        cfg = settings_dict or self.get_settings()
        try:
            # 1. AI Model
            model_cfg = cfg.get("model", {})
            profile_id = model_cfg.get("selected_profile")
            if profile_id and profile_id in ["constructelligence", "vyra"]:
                active_id = get_active_model_id()
                controller = get_monitoring_controller()
                if profile_id != active_id and not controller.is_running:
                    try:
                        controller.switch_model(profile_id)
                        logger.info(f"Synchronized active AI model profile to: {profile_id}")
                    except Exception as e:
                        logger.error(f"Failed to switch model profile to {profile_id}: {e}")

            # 2. PPE Detection Parameters
            ppe_cfg = cfg.get("ppe", {})
            global_conf = float(ppe_cfg.get("global_confidence", 0.20))
            min_ioa = float(ppe_cfg.get("min_ioa", 0.15))
            duration = float(ppe_cfg.get("violation_duration", 5.0))
            enabled_cats = ppe_cfg.get("enabled_categories", ["hardhat", "safety_vest"])
            cat_confs = ppe_cfg.get("category_confidence", {})

            monitoring_service = get_monitoring_service()
            monitoring_service.set_confidence_threshold(global_conf)

            if hasattr(monitoring_service, "association_service"):
                monitoring_service.association_service.min_ioa_threshold = min_ioa

            if hasattr(monitoring_service, "compliance_service"):
                comp = monitoring_service.compliance_service
                comp.min_confidence = global_conf
                comp.set_required_categories(enabled_cats)
                comp.set_category_thresholds(cat_confs)

            if hasattr(monitoring_service, "violation_timer_service"):
                monitoring_service.violation_timer_service.default_threshold_seconds = duration

            # 3. Alert Settings
            alerts_cfg = cfg.get("alerts", {})
            alarm_svc = monitoring_service.alarm_service
            if alarm_svc:
                alarm_svc.sound_enabled = bool(alerts_cfg.get("sound_enabled", True))
                alarm_svc.sound_duration_ms = int(alerts_cfg.get("duration_ms", 400))
                alarm_svc.sound_frequency_hz = int(alerts_cfg.get("frequency_hz", 1000))
                alarm_svc.cooldown_seconds = float(alerts_cfg.get("cooldown_seconds", 10.0))
                alarm_svc.visual_alerts_enabled = bool(alerts_cfg.get("visual_enabled", True))

            # 4. Storage & Evidence
            storage_cfg = cfg.get("storage", {})
            evidence_svc = get_evidence_service()
            if evidence_svc:
                evidence_svc.image_capture_enabled = bool(storage_cfg.get("image_capture_enabled", True))

            # 5. Automatic Email Notifications
            email_cfg = cfg.get("email", {})
            if email_cfg:
                email_svc = get_email_service()
                if email_svc:
                    email_svc.update_config(email_cfg)

            logger.info("Successfully applied configuration settings to all live engines.")
        except Exception as e:
            logger.error(f"Error applying configuration settings: {e}", exc_info=True)

    def get_sanitized_models(self) -> Dict[str, Any]:
        """
        Returns sanitized model profiles that never leak raw HuggingFace repository IDs
        or filenames to the frontend.
        """
        active_id = get_active_model_id()
        controller = get_monitoring_controller()

        profiles = []
        for p in SANITIZED_MODEL_PROFILES:
            item = copy.deepcopy(p)
            item["is_active"] = (p["profile_id"] == active_id)
            profiles.append(item)

        return {
            "active_profile_id": active_id,
            "is_monitoring_running": controller.is_running,
            "profiles": profiles,
        }

    def activate_model_profile(self, profile_id: str) -> Dict[str, Any]:
        """
        Safely activates a sanitized model profile. Rejects if monitoring is running.
        """
        controller = get_monitoring_controller()
        if controller.is_running:
            return {
                "success": False,
                "message": "Cannot switch detection model while camera monitoring is running. Please stop monitoring first.",
                "active_profile_id": get_active_model_id(),
            }

        valid_ids = [p["profile_id"] for p in SANITIZED_MODEL_PROFILES]
        if profile_id not in valid_ids:
            return {
                "success": False,
                "message": f"Invalid model profile '{profile_id}'. Valid profiles: {', '.join(valid_ids)}",
                "active_profile_id": get_active_model_id(),
            }

        try:
            controller.switch_model(profile_id)

            # Persist selected profile into settings
            with self._lock:
                self._current_settings.setdefault("model", {})["selected_profile"] = profile_id
                try:
                    self.settings_file.write_text(json.dumps(self._current_settings, indent=2), encoding="utf-8")
                except Exception as e:
                    logger.warning(f"Could not persist model switch to settings.json: {e}")

            profile_name = next((p["name"] for p in SANITIZED_MODEL_PROFILES if p["profile_id"] == profile_id), profile_id)
            return {
                "success": True,
                "message": f"Successfully activated {profile_name}.",
                "active_profile_id": profile_id,
            }
        except Exception as e:
            logger.error(f"Failed to activate model profile {profile_id}: {e}", exc_info=True)
            return {
                "success": False,
                "message": f"Model activation error: {str(e)}",
                "active_profile_id": get_active_model_id(),
            }

    def test_camera_device(self, camera_index: int = 0, backend: str = "DirectShow") -> Dict[str, Any]:
        """
        Safely tests camera availability by opening it, querying properties, reading 1 test frame,
        and immediately releasing the device. NEVER starts monitoring.
        """
        controller = get_monitoring_controller()
        if controller.is_running:
            return {
                "success": True,
                "available": True,
                "in_use": True,
                "message": f"Camera index {camera_index} is currently actively in use by live monitoring.",
                "resolution": "Active Live Feed",
                "fps": controller._current_fps or 30.0,
            }

        cap = None
        t0 = time.perf_counter()
        try:
            use_dshow = (platform.system() == "Windows" and backend.lower() == "directshow")
            if use_dshow:
                cap = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)
                if not cap or not cap.isOpened():
                    if cap:
                        cap.release()
                    cap = cv2.VideoCapture(camera_index)
            else:
                cap = cv2.VideoCapture(camera_index)

            if not cap or not cap.isOpened():
                return {
                    "success": False,
                    "available": False,
                    "in_use": False,
                    "message": f"Camera index {camera_index} is not connected or could not be opened.",
                }

            w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = float(cap.get(cv2.CAP_PROP_FPS))
            if fps <= 0:
                fps = 30.0

            ret, frame = cap.read()
            latency_ms = round((time.perf_counter() - t0) * 1000.0, 1)

            if not ret or frame is None or frame.size == 0:
                return {
                    "success": False,
                    "available": False,
                    "in_use": False,
                    "message": f"Camera index {camera_index} opened but failed to capture a test frame.",
                }

            return {
                "success": True,
                "available": True,
                "in_use": False,
                "message": f"Camera {camera_index} is operational ({w}x{h} @ {fps:.0f} FPS, test response: {latency_ms}ms).",
                "resolution": f"{w}x{h}",
                "fps": fps,
                "latency_ms": latency_ms,
            }
        except Exception as e:
            return {
                "success": False,
                "available": False,
                "in_use": False,
                "message": f"Camera availability test exception: {str(e)}",
            }
        finally:
            if cap is not None:
                try:
                    cap.release()
                except Exception:
                    pass

    def scan_camera_devices(self, max_devices: int = 4) -> List[Dict[str, Any]]:
        """
        Scans potential camera indices (0 to max_devices-1) to detect connected cameras.
        """
        devices = []
        controller = get_monitoring_controller()
        active_idx = controller._camera_index if controller.is_running else None

        for idx in range(max_devices):
            if active_idx == idx:
                devices.append({
                    "index": idx,
                    "name": f"Camera {idx} (In Active Use)",
                    "available": True,
                    "in_use": True,
                })
                continue

            cap = None
            try:
                if platform.system() == "Windows":
                    cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
                    if not cap or not cap.isOpened():
                        if cap:
                            cap.release()
                        cap = cv2.VideoCapture(idx)
                else:
                    cap = cv2.VideoCapture(idx)

                if cap and cap.isOpened():
                    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                    label = f"Camera {idx} ({w}x{h})" if (w > 0 and h > 0) else f"Camera {idx}"
                    devices.append({
                        "index": idx,
                        "name": label,
                        "available": True,
                        "in_use": False,
                    })
                else:
                    devices.append({
                        "index": idx,
                        "name": f"Camera {idx} (Not Detected)",
                        "available": False,
                        "in_use": False,
                    })
            except Exception:
                devices.append({
                    "index": idx,
                    "name": f"Camera {idx} (Not Detected)",
                    "available": False,
                    "in_use": False,
                })
            finally:
                if cap is not None:
                    try:
                        cap.release()
                    except Exception:
                        pass

        return devices

    def get_system_metrics(self) -> Dict[str, Any]:
        """
        Gathers comprehensive real-time system performance metrics using psutil,
        PyTorch, and monitoring service performance stats. Never fabricates fake GPU metrics.
        """
        # 1. CPU Metrics
        cpu_pct = psutil.cpu_percent(interval=None)
        cpu_physical = psutil.cpu_count(logical=False) or 0
        cpu_logical = psutil.cpu_count(logical=True) or 0
        cpu_freq_obj = psutil.cpu_freq()
        cpu_freq_mhz = round(cpu_freq_obj.current, 1) if cpu_freq_obj else 0.0

        # 2. RAM Metrics
        vm = psutil.virtual_memory()
        ram_total_gb = round(vm.total / (1024 ** 3), 2)
        ram_used_gb = round(vm.used / (1024 ** 3), 2)
        ram_free_gb = round(vm.available / (1024 ** 3), 2)
        ram_pct = vm.percent

        # Backend process memory RSS
        try:
            proc = psutil.Process(os.getpid())
            rss_mb = round(proc.memory_info().rss / (1024 * 1024), 1)
        except Exception:
            rss_mb = 0.0

        # 3. GPU Metrics (Never invent fake GPU stats)
        has_cuda = torch.cuda.is_available()
        if has_cuda:
            try:
                gpu_name = torch.cuda.get_device_name(0)
                mem_alloc = torch.cuda.memory_allocated(0)
                mem_total = torch.cuda.get_device_properties(0).total_memory
                gpu_metrics = {
                    "available": True,
                    "name": gpu_name,
                    "vram_total_mb": round(mem_total / (1024 * 1024), 1),
                    "vram_used_mb": round(mem_alloc / (1024 * 1024), 1),
                    "vram_percent": round((mem_alloc / mem_total) * 100, 1) if mem_total > 0 else 0.0,
                    "status": "Active (CUDA Acceleration)",
                }
            except Exception as e:
                gpu_metrics = {
                    "available": False,
                    "name": "N/A",
                    "vram_total_mb": 0,
                    "vram_used_mb": 0,
                    "vram_percent": 0.0,
                    "status": f"Query Error: {str(e)}",
                }
        else:
            gpu_metrics = {
                "available": False,
                "name": "N/A",
                "vram_total_mb": 0,
                "vram_used_mb": 0,
                "vram_percent": 0.0,
                "status": "N/A (CPU Inference Execution)",
            }

        # 4. AI Model & Pipeline Performance
        monitoring_svc = get_monitoring_service()
        model_perf = monitoring_svc.get_performance_metrics()
        model_init_time_sec = get_model_init_time()
        model_init_ms = round(model_init_time_sec * 1000.0, 1) if model_init_time_sec is not None else 0.0

        # 5. Camera & Controller Performance
        controller = get_monitoring_controller()
        cam_status = controller.get_status()

        # 6. Disk Storage Metrics
        evidence_svc = get_evidence_service()
        storage_stats = evidence_svc.get_storage_stats()

        # 7. Performance status indicator (Normal, Moderate, High, Critical)
        perf_status = "Normal"
        if cpu_pct > 92 or ram_pct > 92:
            perf_status = "Critical"
        elif cpu_pct > 80 or ram_pct > 85 or model_perf["latest_inference_latency_ms"] > 250:
            perf_status = "High"
        elif cpu_pct > 65 or ram_pct > 75 or model_perf["latest_inference_latency_ms"] > 120:
            perf_status = "Moderate"

        return {
            "timestamp": time.time(),
            "performance_status": perf_status,
            "cpu": {
                "percent": cpu_pct,
                "physical_cores": cpu_physical,
                "logical_cores": cpu_logical,
                "frequency_mhz": cpu_freq_mhz,
            },
            "ram": {
                "total_gb": ram_total_gb,
                "used_gb": ram_used_gb,
                "free_gb": ram_free_gb,
                "percent": ram_pct,
                "backend_process_rss_mb": rss_mb,
            },
            "gpu": gpu_metrics,
            "ai_pipeline": {
                "model_init_ms": model_init_ms,
                "latest_inference_latency_ms": model_perf["latest_inference_latency_ms"],
                "avg_inference_latency_ms": model_perf["avg_inference_latency_ms"],
                "max_inference_latency_ms": model_perf["max_inference_latency_ms"],
                "avg_frame_time_ms": model_perf["avg_frame_time_ms"],
                "fps": model_perf["fps"],
                "total_detections": model_perf["total_detections"],
                "confidence_threshold": model_perf["confidence_threshold"],
            },
            "camera": {
                "is_running": cam_status["is_running"],
                "camera_index": cam_status["camera_index"],
                "fps": cam_status["current_fps"],
                "frames_processed": cam_status["frames_processed"],
                "uptime_seconds": cam_status["uptime_seconds"],
            },
            "storage": storage_stats,
        }

    def get_email_settings(self, mask_password: bool = True) -> Dict[str, Any]:
        """Returns email configuration settings with masked password."""
        email_svc = get_email_service()
        return email_svc.get_config(mask_password=mask_password)

    def update_email_settings(self, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Validates, persists, and immediately applies email settings."""
        self.save_settings({"email": updates})
        email_svc = get_email_service()
        return email_svc.get_config(mask_password=True)

    def send_test_email(self, recipient: Optional[str] = None) -> Tuple[bool, str]:
        """Triggers an immediate test email to verify SMTP delivery."""
        email_svc = get_email_service()
        return email_svc.send_test_email(custom_recipient=recipient)


# Singleton instance
_settings_service_instance: Optional[SettingsService] = None


def get_settings_service() -> SettingsService:
    """Returns the shared SettingsService singleton."""
    global _settings_service_instance
    if _settings_service_instance is None:
        _settings_service_instance = SettingsService()
    return _settings_service_instance
