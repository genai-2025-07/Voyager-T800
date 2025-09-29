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


class OpenAISettings(BaseConfigModel):
    api_key: Optional[str] = None
    model_name: str = Field(...)
    temperature: float = Field(...)
    base_url: Optional[str] = None


class GroqSettings(BaseConfigModel):
    api_key: Optional[str] = None
    model_name: str = Field(...)
    temperature: float = Field(...)


class ModelSettings(BaseConfigModel):
    openai: Optional[OpenAISettings] = None
    groq: Optional[GroqSettings] = None


class EmbeddingSettings(BaseConfigModel): # Assuming BaseConfigModel for extra="forbid"
    provider: str = Field(...)
    model: str = Field(...)
    input_dir: str = Field(...)
    output_dir: str = Field(...)
    metadata_csv_path: str = Field(...)
    max_tokens: int = Field(..., description="Max tokens per chunk before splitting.")
    overlap_ratio: float = Field(..., ge=0.0, lt=1.0, description="Chunk overlap ratio (0-1).")
    batch_size: int = Field(..., gt=0, description="Batch size for embedding API calls.")
    polite_delay: float = Field(..., ge=0.0, description="Delay (seconds) between batch API calls.")
    retry_attempts: int = Field(..., ge=0, description="Number of retry attempts for failed API calls.")
    retry_min_wait: float = Field(..., ge=0.0, description="Minimum wait time between retries (seconds).")
    retry_max_wait: float = Field(..., ge=0.0, description="Maximum wait time between retries (seconds).")
    chunking_method: Literal["sliding", "paragraph"] = Field(..., description="Method for data chunking: 'sliding' or 'paragraph'.")
    cleaning_version: str = Field(..., description="Data cleaning configuration version.")
    supported_extensions: list[str] = Field(default_factory=supported_extensions_factory, description="Supported input file extensions.")


class ChromaSettings(BaseConfigModel):
    persist_directory: str = Field(...)
    collection: str = Field(...)


class WeaviateSettings(BaseConfigModel):
    url: str = Field(...)
    api_key: Optional[str] = None
    class_name: str = Field(...)


class VectorDBSettings(BaseConfigModel):
    provider: Literal["chroma", "weaviate"] = Field(...)
    chroma: Optional[ChromaSettings] = None
    weaviate: Optional[WeaviateSettings] = None


class SummaryMemorySettings(BaseConfigModel):
    summary_trigger_count: int = Field(..., gt=0, description="Number of turns after which summary is triggered.")
    max_token_limit: int = Field(..., gt=0, description="Maximum token limit for conversation summary memory.")


class PromptSettings(BaseConfigModel):
    itinerary_template_path: str = Field(..., description="Path to the itinerary prompt file.")
    summary_template_path: str = Field(..., description="Path to the summary prompt file.")


class WeatherSettings(BaseConfigModel):
    api_key: Optional[str] = None
    base_url: str = Field(..., description="Base URL for the OpenWeather API.")
    units: str = Field(..., description="Temperature units")
    request_timeout_seconds: float = Field(..., gt=0, description="HTTP timeout per request.")
    cache_ttl_seconds: int = Field(..., ge=0, description="In-memory cache TTL for forecasts.")
    retry_attempts: int = Field(..., ge=0, description="Number of retry attempts on failure.")
    retry_backoff_min: float = Field(..., ge=0.0, description="Min backoff seconds for retries.")
    retry_backoff_max: float = Field(..., ge=0.0, description="Max backoff seconds for retries.")


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


class AttractionParserSettings(BaseConfigModel):
    csv_file: str = Field(..., description="Path to the CSV file containing attraction data.")
    debug_mode: bool = Field(..., description="Enable debug mode with additional logging and file output.")
    output_dir: str = Field(..., description="Directory where processed text files will be saved.")
    metadata_file: str = Field(..., description="Path to the CSV file where metadata will be saved.")
    remove_non_latin: bool = Field(..., description="Enable/disable non-Latin removal.")
    preserve_mixed_words: bool = Field(..., description="Preserve words with mixed scripts during filtering.")
    aggressive_filtering: bool = Field(..., description="Use character-level filtering (more aggressive) for non-Latin removal.")
    use_see_also: bool = Field(..., description="Whether to include 'See also' sections in extracted text.")
    wikipedia_api_url: str = Field(..., description="Wikipedia API endpoint URL.")
    user_agent: str = Field(..., description="User-Agent string for Wikipedia API requests.")
    rate_limit_delay: float = Field(..., ge=0.0, description="Delay (seconds) between attraction processing to avoid rate limits.")
    summary_max_length: int = Field(..., gt=0, description="Maximum length of the generated summary.")


class Settings(BaseConfigModel):
    app: AppSettings = Field(default_factory=AppSettings)
    model: ModelSettings = Field(default_factory=ModelSettings)
    embedding: EmbeddingSettings = Field(default_factory=EmbeddingSettings)
    vectordb: VectorDBSettings = Field(default_factory=VectorDBSettings)
    bedrock: BedrockSettings = Field(default_factory=BedrockSettings)
    attraction_parser: AttractionParserSettings = Field(default_factory=AttractionParserSettings)
    summary_memory: SummaryMemorySettings = Field(default_factory=SummaryMemorySettings)
    prompt: PromptSettings = Field(default_factory=PromptSettings)
    weather: Optional[WeatherSettings] = None
    logging_config_file: Optional[str] = Field(default=None)


__all__ = [
    "AppSettings",
    "OpenAISettings",
    "GroqSettings",
    "ModelSettings",
    "EmbeddingSettings",
    "VectorDBSettings",
    "ChromaSettings",
    "WeaviateSettings",
    "BedrockSettings",
    "AttractionParserSettings",
    "SummaryMemorySettings",
    "PromptSettings",
    "WeatherSettings",
    "Settings",
]


