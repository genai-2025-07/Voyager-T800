import pytest
from pydantic import ValidationError

from app.config.config_models import (
    BaseConfigModel,
    AppSettings,
    OpenAISettings,
    GroqSettings,
    ModelSettings,
    EmbeddingSettings,
    ChromaSettings,
    WeaviateSettings,
    VectorDBSettings,
    BedrockSettings,
    Settings,
)

# Test BaseConfigModel for extra="forbid"
def test_base_config_model_forbids_extra_fields():
    class TestModel(BaseConfigModel):
        field1: str

    with pytest.raises(ValidationError) as exc_info:
        TestModel(field1="value", extra_field="forbidden")
    assert "Extra inputs are not permitted" in str(exc_info.value)


# Test AppSettings
def test_app_settings_valid():
    settings = AppSettings(name="test_app", env="prod", version="1.0.0", api_key="abc")
    assert settings.name == "test_app"
    assert settings.env == "prod"
    assert settings.version == "1.0.0"
    assert settings.api_key == "abc"

def test_app_settings_defaults():
    settings = AppSettings()
    assert settings.name == "voyager-t800"
    assert settings.env == "dev"
    assert settings.version == "0.1.0"
    assert settings.api_key is None

def test_app_settings_invalid_env():
    with pytest.raises(ValidationError):
        AppSettings(env="invalid")

def test_app_settings_forbids_extra():
    with pytest.raises(ValidationError):
        AppSettings(name="test", extra_field="bad")

# Test OpenAISettings
def test_openai_settings_valid():
    settings = OpenAISettings(api_key="sk-123", model_name="gpt-4", temperature=0.5, base_url="http://localhost")
    assert settings.api_key == "sk-123"
    assert settings.model_name == "gpt-4"
    assert settings.temperature == 0.5
    assert settings.base_url == "http://localhost"

def test_openai_settings_defaults():
    settings = OpenAISettings()
    assert settings.api_key is None
    assert settings.model_name == "text-embedding-3-small"
    assert settings.temperature == 0.7
    assert settings.base_url is None

# Test GroqSettings
def test_groq_settings_valid():
    settings = GroqSettings(api_key="gq-123", model_name="llama3-70b", temperature=0.1)
    assert settings.api_key == "gq-123"
    assert settings.model_name == "llama3-70b"
    assert settings.temperature == 0.1

def test_groq_settings_defaults():
    settings = GroqSettings()
    assert settings.api_key is None
    assert settings.model_name == "llama3-8b-8192"
    assert settings.temperature == 0.7

# Test ModelSettings
def test_model_settings_valid():
    settings = ModelSettings(
        openai={"model_name": "gpt-3.5"},
        groq={"temperature": 0.9}
    )
    assert settings.openai.model_name == "gpt-3.5"
    assert settings.groq.temperature == 0.9
    assert settings.openai.temperature == 0.7 # Default still applies

def test_model_settings_defaults():
    settings = ModelSettings()
    assert isinstance(settings.openai, OpenAISettings)
    assert isinstance(settings.groq, GroqSettings)

# Test EmbeddingSettings (assuming recommended additions)
def test_embedding_settings_valid():
    settings = EmbeddingSettings(
        provider="openai",
        model="text-embedding-3-large",
        input_dir="data/docs",
        output_dir="data/output_embeddings",
        metadata_csv_path="data/meta.csv",
        max_tokens=500,
        overlap_ratio=0.3,
        batch_size=100,
        polite_delay=0.2,
        retry_attempts=3,
        retry_min_wait=2.0,
        retry_max_wait=60.0,
        chunking_method="paragraph",
        cleaning_version="v2.0",
        supported_extensions={".md", ".pdf"}
    )
    assert settings.provider == "openai"
    assert settings.model == "text-embedding-3-large"
    assert settings.max_tokens == 500
    assert settings.overlap_ratio == 0.3
    assert settings.chunking_method == "paragraph"
    assert settings.supported_extensions == {".md", ".pdf"}

def test_embedding_settings_invalid_overlap_ratio():
    with pytest.raises(ValidationError):
        EmbeddingSettings(overlap_ratio=1.1)
    with pytest.raises(ValidationError):
        EmbeddingSettings(overlap_ratio=-0.1)

def test_embedding_settings_invalid_chunking_method():
    with pytest.raises(ValidationError):
        EmbeddingSettings(chunking_method="unknown")

# Test ChromaSettings
def test_chroma_settings_valid():
    settings = ChromaSettings(persist_directory="/tmp/chroma_db", collection="my_collection")
    assert settings.persist_directory == "/tmp/chroma_db"
    assert settings.collection == "my_collection"

# Test WeaviateSettings
def test_weaviate_settings_valid():
    settings = WeaviateSettings(url="http://weaviate:8080", api_key="weaviate-key", class_name="MyClass")
    assert settings.url == "http://weaviate:8080"
    assert settings.api_key == "weaviate-key"
    assert settings.class_name == "MyClass"

# Test VectorDBSettings
def test_vectordb_settings_valid_chroma():
    settings = VectorDBSettings(provider="chroma", chroma={"collection": "test_chroma"})
    assert settings.provider == "chroma"
    assert settings.chroma.collection == "test_chroma"
    assert settings.weaviate.url == "http://localhost:8080" # Default

def test_vectordb_settings_valid_weaviate():
    settings = VectorDBSettings(provider="weaviate", weaviate={"url": "http://my-weaviate:8080"})
    assert settings.provider == "weaviate"
    assert settings.weaviate.url == "http://my-weaviate:8080"
    assert settings.chroma.collection == "voyager" # Default

def test_vectordb_settings_invalid_provider():
    with pytest.raises(ValidationError):
        VectorDBSettings(provider="invalid_db")

# Test BedrockSettings
def test_bedrock_settings_valid():
    settings = BedrockSettings(
        enabled=True,
        region_name="us-east-1",
        model_id="anthropic.claude-v2",
        temperature=0.1,
        max_tokens=512,
        top_p=0.8,
        top_k=10
    )
    assert settings.enabled is True
    assert settings.region_name == "us-east-1"
    assert settings.model_id == "anthropic.claude-v2"
    assert settings.temperature == 0.1
    assert settings.max_tokens == 512
    assert settings.top_p == 0.8
    assert settings.top_k == 10

def test_bedrock_settings_defaults():
    settings = BedrockSettings()
    assert settings.enabled is False
    assert settings.temperature == 0.7
    assert settings.max_tokens == 1024
    assert settings.top_p is None
    assert settings.top_k is None

# Test top-level Settings
def test_full_settings_valid():
    full_config = {
        "app": {"name": "full_test", "env": "prod"},
        "model": {"openai": {"temperature": 0.1}},
        "embedding": {"max_tokens": 200},
        "vectordb": {"provider": "weaviate", "weaviate": {"class_name": "MyVoyager"}},
        "bedrock": {"enabled": True, "region_name": "us-west-2"},
        "logging_config_file": "my_logger.yaml"
    }
    settings = Settings(**full_config)
    assert settings.app.name == "full_test"
    assert settings.model.openai.temperature == 0.1
    assert settings.embedding.max_tokens == 200
    assert settings.vectordb.provider == "weaviate"
    assert settings.vectordb.weaviate.class_name == "MyVoyager"
    assert settings.bedrock.enabled is True
    assert settings.logging_config_file == "my_logger.yaml"

def test_full_settings_forbids_extra():
    with pytest.raises(ValidationError):
        Settings(app={"extra_field": "bad"})

    with pytest.raises(ValidationError):
        Settings(extra_top_level="bad")