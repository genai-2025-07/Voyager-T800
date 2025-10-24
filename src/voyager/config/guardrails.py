"""
Guardrails configuration for Voyager agent.
Defines budget limits, timeouts, and safety thresholds.
"""

from pydantic_settings import BaseSettings
from typing import Optional


class GuardrailsSettings(BaseSettings):
    """Budget and safety limits for agent execution"""
    
    # Agent budget enforcement
    MAX_TOOL_CALLS: int = 15
    MAX_PAID_CALLS: int = 10  # LLM API calls that cost money
    PER_CALL_TIMEOUT: int = 30  # seconds
    
    # S3 Image settings
    S3_THUMBNAIL_BUCKET: Optional[str] = None
    PRESIGNED_URL_TTL: int = 3600  # 1 hour
    MAX_IMAGE_SIZE_MB: int = 10
    
    # Secrets Manager
    SECRETS_MANAGER_SECRET_NAME: str = "voyager/api-keys"
    KMS_KEY_ALIAS: str = "alias/voyager-secrets"
    
    # Cost alerting
    MONTHLY_BUDGET_USD: int = 100
    BUDGET_ALERT_THRESHOLD_PERCENT: int = 80
    
    class Config:
        env_file = ".env"
        case_sensitive = True


# Global instance
guardrails_settings = GuardrailsSettings()