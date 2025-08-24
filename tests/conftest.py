import pytest
from pathlib import Path
from typing import Dict, Any

@pytest.fixture
def temp_config_dir(tmp_path: Path) -> Path:
    """
    Provides a temporary directory for config files.
    """
    return tmp_path / "app" / "config"

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
def mock_project_root(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """
    Mocks the project root to control where the ConfigLoader looks for config files.
    """
    # Create a dummy app/config directory within the tmp_path
    mock_app_config_dir = tmp_path / "app" / "config"
    mock_app_config_dir.mkdir(parents=True, exist_ok=True)

    from app.config.loader import ConfigLoader
    monkeypatch.setattr(ConfigLoader, "project_root", tmp_path)

    # Also ensure the default.yaml path is correctly resolved relative to this root
    monkeypatch.setattr(ConfigLoader, "base_config_path", mock_app_config_dir / "default.yaml")
    monkeypatch.setattr(ConfigLoader, "config_dir", mock_app_config_dir)

    return tmp_path

@pytest.fixture
def dummy_prompt_file(tmp_path: Path) -> Path:
    """Creates a dummy prompt file."""
    prompt_dir = tmp_path / "app" / "prompts"
    prompt_dir.mkdir(parents=True, exist_ok=True)
    prompt_file = prompt_dir / "test_itinerary_prompt.txt"
    prompt_file.write_text("Hello {user_input} from {chat_history}")
    return prompt_file