from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class BaseConfigModel(BaseModel):
    model_config = {
        "extra": "forbid",
    }


class AppSettings(BaseConfigModel):
    name: str = Field(default="voyager-t800")
    env: Literal["dev", "prod", "test"] = Field(default="dev")
    version: str = Field(default="0.1.0")
    api_key: Optional[str] = None


class OpenAISettings(BaseConfigModel):
    api_key: Optional[str] = None
    model_name: str = Field(default="text-embedding-3-small")
    temperature: float = Field(default=0.7)
    base_url: Optional[str] = None


class GroqSettings(BaseConfigModel):
    api_key: Optional[str] = None
    model_name: str = Field(default="llama3-8b-8192")
    temperature: float = Field(default=0.7)


class ModelSettings(BaseConfigModel):
    openai: OpenAISettings = Field(default_factory=OpenAISettings)
    groq: GroqSettings = Field(default_factory=GroqSettings)


class EmbeddingSettings(BaseConfigModel): # Assuming BaseConfigModel for extra="forbid"
    provider: str = Field(default="openai")
    model: str = Field(default="text-embedding-3-small")
    input_dir: str = Field(default="data/raw")
    output_dir: str = Field(default="data/embeddings")
    metadata_csv_path: str = Field(default="data/metadata.csv")
    max_tokens: int = Field(default=450, description="Max tokens per chunk before splitting.")
    overlap_ratio: float = Field(default=0.2, ge=0.0, lt=1.0, description="Chunk overlap ratio (0-1).")
    batch_size: int = Field(default=64, gt=0, description="Batch size for embedding API calls.")
    polite_delay: float = Field(default=0.1, ge=0.0, description="Delay (seconds) between batch API calls.")
    retry_attempts: int = Field(default=5, ge=0, description="Number of retry attempts for failed API calls.")
    retry_min_wait: float = Field(default=1.0, ge=0.0, description="Minimum wait time between retries (seconds).")
    retry_max_wait: float = Field(default=30.0, ge=0.0, description="Maximum wait time between retries (seconds).")
    chunking_method: Literal["sliding", "paragraph"] = Field(default="sliding", description="Method for data chunking: 'sliding' or 'paragraph'.")
    cleaning_version: str = Field(default="v1.2", description="Data cleaning configuration version.")
    supported_extensions: set[str] = Field(default_factory=lambda: {'.txt', '.json'}, description="Supported input file extensions.")


class Settings(BaseConfigModel):
    app: AppSettings = Field(default_factory=AppSettings)
    model: ModelSettings = Field(default_factory=ModelSettings)
    embedding: EmbeddingSettings = Field(default_factory=EmbeddingSettings)
    logging_config_file: Optional[str] = Field(default=None)


class ChromaSettings(BaseConfigModel):
    persist_directory: str = Field(default=".chroma")
    collection: str = Field(default="voyager")


class WeaviateSettings(BaseConfigModel):
    url: str = Field(default="http://localhost:8080")
    api_key: Optional[str] = None
    class_name: str = Field(default="voyager")


class VectorDBSettings(BaseConfigModel):
    provider: Literal["chroma", "weaviate"] = Field(default="chroma")
    chroma: ChromaSettings = Field(default_factory=ChromaSettings)
    weaviate: WeaviateSettings = Field(default_factory=WeaviateSettings)


class SummaryMemorySettings(BaseConfigModel):
    summary_trigger_count: int = Field(default=2, gt=0, description="Number of turns after which summary is triggered.")
    max_token_limit: int = Field(default=1000, gt=0, description="Maximum token limit for conversation summary memory.")


class BedrockSettings(BaseConfigModel):
    enabled: bool = Field(default=False)
    region_name: Optional[str] = None
    profile_name: Optional[str] = None
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None
    aws_session_token: Optional[str] = None
    endpoint_url: Optional[str] = None
    model_id: Optional[str] = None
    temperature: float = Field(default=0.7)
    max_tokens: int = Field(default=1024)
    top_p: Optional[float] = None
    top_k: Optional[int] = None


class AttractionParserSettings(BaseConfigModel):
    csv_file: str = Field(default="data/attractions_names_list.csv", description="Path to the CSV file containing attraction data.")
    debug_mode: bool = Field(default=False, description="Enable debug mode with additional logging and file output.")
    output_dir: str = Field(default="data/raw", description="Directory where processed text files will be saved.")
    metadata_file: str = Field(default="data/metadata.csv", description="Path to the CSV file where metadata will be saved.")
    remove_non_latin: bool = Field(default=True, description="Enable/disable non-Latin removal.")
    preserve_mixed_words: bool = Field(default=True, description="Preserve words with mixed scripts during filtering.")
    aggressive_filtering: bool = Field(default=False, description="Use character-level filtering (more aggressive) for non-Latin removal.")
    use_see_also: bool = Field(default=False, description="Whether to include 'See also' sections in extracted text.")
    wikipedia_api_url: str = Field(default="https://en.wikipedia.org/w/api.php", description="Wikipedia API endpoint URL.")
    user_agent: str = Field(default="VoyagerT800AttractionsBot/1.0 (https://example.com/contact)", description="User-Agent string for Wikipedia API requests.")
    rate_limit_delay: float = Field(default=0.5, ge=0.0, description="Delay (seconds) between attraction processing to avoid rate limits.")
    summary_max_length: int = Field(default=200, gt=0, description="Maximum length of the generated summary.")


class Settings(BaseConfigModel):
    app: AppSettings = Field(default_factory=AppSettings)
    model: ModelSettings = Field(default_factory=ModelSettings)
    embedding: EmbeddingSettings = Field(default_factory=EmbeddingSettings)
    vectordb: VectorDBSettings = Field(default_factory=VectorDBSettings)
    bedrock: BedrockSettings = Field(default_factory=BedrockSettings)
    attraction_parser: AttractionParserSettings = Field(default_factory=AttractionParserSettings)
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
    "Settings",
]


