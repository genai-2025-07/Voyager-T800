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


class EmbeddingSettings(BaseConfigModel):
    provider: str = Field(default="openai")
    model: str = Field(default="text-embedding-3-small")
    input_dir: str = Field(default="data/raw")
    output_dir: str = Field(default="data/embeddings")
    metadata_csv_path: str = Field(default="data/metadata.csv")


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


class Settings(BaseConfigModel):
    app: AppSettings = Field(default_factory=AppSettings)
    model: ModelSettings = Field(default_factory=ModelSettings)
    embedding: EmbeddingSettings = Field(default_factory=EmbeddingSettings)
    vectordb: VectorDBSettings = Field(default_factory=VectorDBSettings)
    bedrock: BedrockSettings = Field(default_factory=BedrockSettings)
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
    "Settings",
]


