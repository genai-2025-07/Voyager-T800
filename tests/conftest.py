import pytest
from pathlib import Path
from typing import Dict, Any

@pytest.fixture
def temp_config_dir(tmp_path: Path) -> Path:
    """
    Provides a temporary directory for config files.
    """
    mock_app_config_dir = tmp_path / "app" / "config"
    mock_app_config_dir.mkdir(parents=True, exist_ok=True)
    return mock_app_config_dir

@pytest.fixture
def create_yaml_file():
    """
    A factory fixture to create YAML files in a given directory.
    """
    def _create_yaml(directory: Path, filename: str, content: Dict[str, Any]) -> Path:
        filepath = directory / filename
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, "w") as f:
            import yaml
            yaml.dump(content, f)
        return filepath
    return _create_yaml

@pytest.fixture
def set_env(monkeypatch: pytest.MonkeyPatch):
    """
    A fixture to temporarily set environment variables for a test.
    """
    def _set_env_vars(env_vars: Dict[str, str]):
        for key, value in env_vars.items():
            monkeypatch.setenv(key, value)
    return _set_env_vars

@pytest.fixture(autouse=True)
def cleanup_env_vars(monkeypatch: pytest.MonkeyPatch):
    """
    Ensures environment variables are cleaned up after each test.
    """
    # This fixture ensures any env vars set during a test are removed or reverted
    # by monkeypatch's autouse behavior.
    pass

@pytest.fixture
def dummy_prompt_file(tmp_path: Path) -> Path:
    """Creates a dummy prompt file."""
    prompt_dir = tmp_path / "app" / "prompts"
    prompt_dir.mkdir(parents=True, exist_ok=True)
    prompt_file = prompt_dir / "test_itinerary_prompt.txt"
    prompt_file.write_text("Hello {user_input} from {chat_history}")
    return prompt_file

@pytest.fixture
def dummy_config_content() -> Dict[str, Any]:
    """Creates a dummy config file."""
    return {
        "app": {
            "name": "voyager-t800",
            "env": "dev",
            "version": "0.1.0",
            "api_key": None,
        },
        "model": {
            "openai": {
                "api_key": None,
                "model_name": "text-embedding-3-small",
                "temperature": 0.7,
                "base_url": None,
            },
            "groq": {
                "api_key": None,
                "model_name": "llama3-8b-8192",
                "temperature": 0.7,
            },
        },
        "embedding": {
            "provider": "openai",
            "model": "text-embedding-3-small",
            "input_dir": "data/raw",
            "output_dir": "data/embeddings",
            "metadata_csv_path": "data/metadata.csv",
            "max_tokens": 450,
            "overlap_ratio": 0.2,
            "batch_size": 64,
            "polite_delay": 0.1,
            "retry_attempts": 5,
            "retry_min_wait": 1.0,
            "retry_max_wait": 30.0,
            "chunking_method": "sliding",
            "cleaning_version": "v1.2",
            "supported_extensions": [".txt", ".json"],
        },
        "vectordb": {
            "provider": "chroma",
            "chroma": {
                "persist_directory": ".chroma",
                "collection": "voyager",
            },
            "weaviate": {
                "url": "http://localhost:8080",
                "api_key": None,
                "class_name": "voyager",
            },
        },
        "bedrock": {
            "enabled": False,
            "region_name": None,
            "profile_name": None,
            "aws_access_key_id": None,
            "aws_secret_access_key": None,
            "aws_session_token": None,
            "endpoint_url": None,
            "model_id": None,
            "temperature": 0.7,
            "max_tokens": 1024,
            "top_p": None,
            "top_k": None,
        },
        "attraction_parser": {
            "csv_file": "data/attractions_names_list.csv",
            "debug_mode": False,
            "output_dir": "data/raw",
            "metadata_file": "data/metadata.csv",
            "remove_non_latin": True,
            "preserve_mixed_words": True,
            "aggressive_filtering": False,
            "use_see_also": False,
            "wikipedia_api_url": "https://en.wikipedia.org/w/api.php",
            "user_agent": "VoyagerT800AttractionsBot/1.0 (https://example.com/contact)",
            "rate_limit_delay": 0.5,
            "summary_max_length": 200,
        },
        "summary_memory": {
            "summary_trigger_count": 2,
            "max_token_limit": 1000,
        },
        "prompt": {
            "itinerary_template_path": "app/prompts/test_itinerary_prompt.txt",
            "summary_template_path": "app/prompts/test_summary_prompt.txt",
        },
        "logging_config_file": None,
    }