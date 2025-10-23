from __future__ import annotations
from typing import Literal, Optional
from pydantic import BaseModel, Field

def supported_extensions_factory() -> list[str]:
    return [".txt", ".json"]

class BaseConfigModel(BaseModel):
    model_config = {
        "extra": "forbid",
    }

class AppSettings(BaseConfigModel):
    name: str = Field(...)
    env: Literal["dev", "prod", "test"] = Field(...)
    version: str = Field(...)
    api_key: Optional[str] = None

class WeatherSettings(BaseConfigModel):
    api_key: Optional[str] = None
    base_url: str = Field(..., description="Base URL for the OpenWeather API.")
    units: str = Field(..., description="Temperature units")
    request_timeout_seconds: float = Field(..., gt=0, description="HTTP timeout per request.")
    cache_ttl_seconds: int = Field(..., ge=0, description="In-memory cache TTL for forecasts.")
    retry_attempts: int = Field(..., ge=0, description="Number of retry attempts on failure.")
    retry_backoff_min: float = Field(..., ge=0.0, description="Min backoff seconds for retries.")
    retry_backoff_max: float = Field(..., ge=0.0, description="Max backoff seconds for retries.")

class ItinerarySettings(BaseConfigModel):
    api_key: Optional[str] = None

class TavilySettings(BaseConfigModel):
    tavily_api_key: Optional[str] = None
    tavily_api_url: str = Field(..., description="API URL for Tavily Search.")
    tavily_max_results: int = Field(..., gt=0, description="Maximum number of results to return.")
    tavily_country: str = Field(..., description="Country to search in.")
    tavily_include_answer: str = Field(..., description="Include answer in the response.")
    tavily_timeout: int = Field(..., gt=0, description="Timeout for the API request in seconds.")

class BedrockSettings(BaseConfigModel):
    enabled: bool = Field(...)
    region_name: Optional[str] = None
    profile_name: Optional[str] = None
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None
    aws_session_token: Optional[str] = None
    endpoint_url: Optional[str] = None
    model_id: Optional[str] = None
    temperature: float = Field(...)
    max_tokens: int = Field(...)
    top_p: Optional[float] = None
    top_k: Optional[int] = None

class CognitoSettings(BaseConfigModel):
    aws_region: str = Field(..., description="AWS region for Cognito service")
    user_pool_id: str = Field(..., description="Cognito User Pool ID")
    client_id: str = Field(..., description="Cognito App Client ID")
    client_secret: Optional[str] = Field(None, description="Cognito App Client Secret (for confidential clients)")
    jwt_algorithm: str = Field(default="RS256", description="JWT signature algorithm")

class Settings(BaseConfigModel):
    app: AppSettings = Field(default_factory=AppSettings)
    bedrock: BedrockSettings = Field(default_factory=BedrockSettings)
    weather: Optional[WeatherSettings] = None
    itinerary: ItinerarySettings = Field(default_factory=ItinerarySettings)
    tavily: Optional[TavilySettings] = None
    cognito: Optional[CognitoSettings] = None
    logging_config_file: Optional[str] = Field(default=None)

__all__ = [
    "AppSettings",
    "BedrockSettings",
    "WeatherSettings",
    "ItinerarySettings",
    "TavilySettings",
    "CognitoSettings",
    "Settings",
]