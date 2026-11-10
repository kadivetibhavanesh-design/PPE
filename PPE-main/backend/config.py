import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file if present
BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / ".env"
if ENV_PATH.exists():
    load_dotenv(ENV_PATH)


class Settings:
    """Application configuration settings."""

    # Project Information
    PROJECT_NAME: str = os.getenv("PROJECT_NAME", "PPE Monitoring System")
    PROJECT_DESCRIPTION: str = os.getenv(
        "PROJECT_DESCRIPTION",
        "AI-Powered Real-Time PPE Detection and Industrial Safety Monitoring System",
    )
    VERSION: str = os.getenv("VERSION", "1.0.0")

    # Server Configuration
    HOST: str = os.getenv("HOST", "127.0.0.1")
    PORT: int = int(os.getenv("PORT", "8000"))
    DEBUG: bool = os.getenv("DEBUG", "False").lower() in ("true", "1", "t")

    # API Configuration
    API_PREFIX: str = "/api"

    # CORS Configuration
    CORS_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    # Device Configuration
    DEVICE: str = "CPU"

    # Storage Paths
    BASE_DIR: Path = BASE_DIR
    BACKEND_DIR: Path = Path(__file__).resolve().parent
    STORAGE_DIR: Path = BACKEND_DIR / "storage"
    EVIDENCE_DIR: Path = STORAGE_DIR / "evidence"
    INCIDENTS_DIR: Path = STORAGE_DIR / "incidents"

    # Automatic Email Alert & Notification Settings
    EMAIL_ENABLED: bool = os.getenv("EMAIL_ENABLED", "False").lower() in ("true", "1", "t")
    EMAIL_RECIPIENT: str = os.getenv("EMAIL_RECIPIENT", "bhavaneshkadiveti@gmail.com")
    SMTP_HOST: str = os.getenv("SMTP_HOST", "")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USERNAME: str = os.getenv("SMTP_USERNAME", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    SMTP_SENDER_EMAIL: str = os.getenv("SMTP_SENDER_EMAIL", "")
    SMTP_USE_TLS: bool = os.getenv("SMTP_USE_TLS", "True").lower() in ("true", "1", "t")
    SMTP_USE_SSL: bool = os.getenv("SMTP_USE_SSL", "False").lower() in ("true", "1", "t")
    EMAIL_REMINDER_INTERVAL_MINUTES: int = int(os.getenv("EMAIL_REMINDER_INTERVAL_MINUTES", "5"))


# Global settings singleton
settings = Settings()

