from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class AppSettings(BaseModel):
    name: str = Field(default="voyager-t800")
    env: Literal["dev", "prod", "test"] = Field(default="dev")
    version: str = Field(default="0.1.0")
    api_key: Optional[str] = None

    model_config = {
        "extra": "ignore",
    }


class OpenAISettings(BaseModel):
    api_key: Optional[str] = None
    model_name: str = Field(default="text-embedding-3-small")
    temperature: float = Field(default=0.7)
    base_url: Optional[str] = None

    model_config = {
        "extra": "ignore",
    }


class GroqSettings(BaseModel):
    api_key: Optional[str] = None
    model_name: str = Field(default="llama3-8b-8192")
    temperature: float = Field(default=0.7)

    model_config = {
        "extra": "ignore",
    }


class ModelSettings(BaseModel):
    openai: OpenAISettings = Field(default_factory=OpenAISettings)
    groq: GroqSettings = Field(default_factory=GroqSettings)

    model_config = {
        "extra": "ignore",
    }


class EmbeddingSettings(BaseModel):
    provider: str = Field(default="openai")
    model: str = Field(default="text-embedding-3-small")
    input_dir: str = Field(default="data/raw")
    output_dir: str = Field(default="data/embeddings")
    metadata_csv_path: str = Field(default="data/metadata.csv")

    model_config = {
        "extra": "ignore",
    }


class Settings(BaseModel):
    app: AppSettings = Field(default_factory=AppSettings)
    model: ModelSettings = Field(default_factory=ModelSettings)
    embedding: EmbeddingSettings = Field(default_factory=EmbeddingSettings)
    logging_config_file: Optional[str] = Field(default=None)

    model_config = {
        "extra": "ignore",
    }


class ChromaSettings(BaseModel):
    persist_directory: str = Field(default=".chroma")
    collection: str = Field(default="voyager")

    model_config = {"extra": "ignore"}


class WeaviateSettings(BaseModel):
    url: str = Field(default="http://localhost:8080")
    api_key: Optional[str] = None
    class_name: str = Field(default="voyager")

    model_config = {"extra": "ignore"}


class VectorDBSettings(BaseModel):
    provider: Literal["chroma", "weaviate"] = Field(default="chroma")
    chroma: ChromaSettings = Field(default_factory=ChromaSettings)
    weaviate: WeaviateSettings = Field(default_factory=WeaviateSettings)

    model_config = {"extra": "ignore"}


class BedrockSettings(BaseModel):
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

    model_config = {"extra": "ignore"}


class Settings(BaseModel):
    app: AppSettings = Field(default_factory=AppSettings)
    model: ModelSettings = Field(default_factory=ModelSettings)
    embedding: EmbeddingSettings = Field(default_factory=EmbeddingSettings)
    vectordb: VectorDBSettings = Field(default_factory=VectorDBSettings)
    bedrock: BedrockSettings = Field(default_factory=BedrockSettings)
    logging_config_file: Optional[str] = Field(default=None)

    model_config = {
        "extra": "ignore",
    }


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


