import os
from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator

class Settings(BaseSettings):
    # Comma-separated list of URLs to keep warm
    BACKEND_URLS_RAW: str = "http://localhost:8000/health"
    
    # Range of interval in minutes for randomized jitter scheduling
    PING_INTERVAL_MIN: float = 10.0
    PING_INTERVAL_MAX: float = 14.0
    
    # HTTP requests configuration
    REQUEST_TIMEOUT_SEC: int = 10
    MAX_RETRIES: int = 3
    BACKOFF_FACTOR: float = 2.0
    
    # Alerting threshold and webhook
    ALERT_WEBHOOK_URL: Optional[str] = None
    CONSECUTIVE_FAILURE_ALERT_THRESHOLD: int = 5
    
    # Security shared secret token
    KEEP_WARM_TOKEN: Optional[str] = None

    # Distributed lock configuration
    REDIS_URL: Optional[str] = None

    # Metrics port for Prometheus scraping
    METRICS_PORT: int = 9000

    # Optional external heartbeat ping URL (e.g. Healthchecks.io)
    HEARTBEAT_URL: Optional[str] = None

    # Circuit breaker cooldown period in minutes
    CIRCUIT_BREAKER_COOLDOWN_MIN: int = 15

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @property
    def BACKEND_URLS(self) -> List[str]:
        return [
            url.strip() 
            for url in self.BACKEND_URLS_RAW.split(",") 
            if url.strip()
        ]

settings = Settings()
