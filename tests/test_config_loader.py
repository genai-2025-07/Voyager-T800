import pytest
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

from app.config.loader import ConfigLoader
from app.config.config_models import Settings, AppSettings, EmbeddingSettings, BedrockSettings
from pydantic import ValidationError


def test_config_loader_init_and_load_base(tmp_path, create_yaml_file, temp_config_dir, dummy_config_content):
    """Test that the ConfigLoader loads the base config correctly."""
    create_yaml_file(temp_config_dir, "default.yaml", dummy_config_content)

    loader = ConfigLoader(project_root=tmp_path)
    settings = loader.get_settings()

    assert settings.app.name == dummy_config_content["app"]["name"]
    assert settings.app.env == dummy_config_content["app"]["env"]
    assert settings.model.openai.model_name == dummy_config_content["model"]["openai"]["model_name"]


def test_config_loader_override_with_file(tmp_path, create_yaml_file, temp_config_dir, dummy_config_content):
    """Test that an override file merges correctly."""
    override_content = {
        "app": {"version": "1.0.0"},
        "embedding": {"provider": "override_provider", "input_dir": "custom_data"},
    }
    create_yaml_file(temp_config_dir, "default.yaml", dummy_config_content)
    override_path = create_yaml_file(temp_config_dir, "test_override.yaml", override_content)

    loader = ConfigLoader(config_path=str(override_path), project_root=tmp_path)
    settings = loader.get_settings()

    assert settings.app.name == dummy_config_content["app"]["name"]
    assert settings.app.version == "1.0.0" # Overridden
    assert settings.embedding.provider == "override_provider" # Overridden
    assert settings.embedding.input_dir == "custom_data" # New field in override


def test_config_loader_env_override_path(tmp_path, create_yaml_file, temp_config_dir, set_env, dummy_config_content):
    """Test that VOYAGER_CONFIG environment variable specifies override path."""
    default_content = dummy_config_content
    env_override_content = {"app": {"name": "env_app"}}

    create_yaml_file(temp_config_dir, "default.yaml", default_content)
    env_override_path = create_yaml_file(temp_config_dir, "env.yaml", env_override_content)

    set_env({"VOYAGER_CONFIG": str(env_override_path)})

    loader = ConfigLoader(project_root=tmp_path)
    settings = loader.get_settings()

    assert settings.app.name == "env_app"


def test_config_loader_app_env_override(tmp_path, create_yaml_file, temp_config_dir, set_env, dummy_config_content):
    """Test that APP_ENV environment variable auto-loads override."""
    default_content = dummy_config_content
    dev_override_content = {"app": {"name": "dev_app", "env": "dev"}}

    create_yaml_file(temp_config_dir, "default.yaml", default_content)
    create_yaml_file(temp_config_dir, "dev.yaml", dev_override_content)

    set_env({"APP_ENV": "dev"})

    loader = ConfigLoader(project_root=tmp_path)
    settings = loader.get_settings()

    assert settings.app.name == "dev_app"
    assert settings.app.env == "dev"


def test_config_loader_env_var_expansion(tmp_path, create_yaml_file, temp_config_dir, set_env, dummy_config_content):
    """Test that environment variables are expanded correctly."""
    default_content = dummy_config_content
    default_content["app"]["name"] = "${APP_NAME}"
    default_content["app"]["version"] = "${APP_VERSION:1.0.0}"
    default_content["bedrock"]["aws_access_key_id"] = "${AWS_ACCESS_KEY_ID}"
    create_yaml_file(temp_config_dir, "default.yaml", default_content)

    set_env({"APP_NAME": "ExpandedApp", "AWS_ACCESS_KEY_ID": "mock_key"})

    loader = ConfigLoader(project_root=tmp_path)
    settings = loader.get_settings()

    assert settings.app.name == "ExpandedApp"
    assert settings.app.version == "1.0.0" # Default value used
    assert settings.bedrock.aws_access_key_id == "mock_key"


def test_config_loader_env_var_expansion_missing_required(tmp_path, create_yaml_file, temp_config_dir):
    """Test that missing required environment variables raise an error."""
    default_content = {
        "app": {"name": "${MISSING_VAR}"}, # No default provided
    }
    create_yaml_file(temp_config_dir, "default.yaml", default_content)

    with pytest.raises(ValueError, match="Environment variable 'MISSING_VAR' is not defined"):
        ConfigLoader(project_root=tmp_path)


def test_config_loader_validation_failure(tmp_path, create_yaml_file, temp_config_dir, dummy_config_content):
    """Test that invalid config values raise Pydantic ValidationError."""
    default_content = dummy_config_content
    default_content["app"]["env"] = "invalid_env_type" # AppSettings.env is Literal["dev", "prod", "test"]
    create_yaml_file(temp_config_dir, "default.yaml", default_content)

    with pytest.raises(ValueError):
        ConfigLoader(project_root=tmp_path)


def test_config_loader_non_dict_yaml(tmp_path, temp_config_dir):
    """Test handling of a YAML file that isn't a top-level dictionary."""
    filepath = temp_config_dir / "default.yaml"
    filepath.parent.mkdir(parents=True, exist_ok=True)
    filepath.write_text("- item1\n- item2")

    with pytest.raises(ValueError, match="Config file must contain a mapping at top-level"):
        ConfigLoader(project_root=tmp_path)
        

def test_config_loader_get_settings_not_initialized(tmp_path):
    """Test that get_settings raises RuntimeError if settings are not initialized."""
    # Create a minimal ConfigLoader that won't call _validate_and_expose
    class MockConfigLoader(ConfigLoader):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.settings = None # Force settings to be None

    # We need to mock the underlying file system operations to prevent actual loading
    with patch('app.config.loader.Path') as MockPath:
        mock_path_instance = MagicMock()
        mock_path_instance.exists.return_value = True # Simulate file exists
        mock_path_instance.open.return_value.__enter__.return_value.read.return_value = "{}" # Return empty content
        MockPath.return_value.__truediv__.return_value = mock_path_instance
        MockPath.return_value.parent.__truediv__.return_value = mock_path_instance

        with patch.object(ConfigLoader, '_load_config', MagicMock()):
            with patch.object(ConfigLoader, '_expand_env_vars', MagicMock()):
                with patch.object(ConfigLoader, '_validate_and_expose', MagicMock()): # Prevent validation
                    loader = ConfigLoader(project_root=tmp_path)
                    loader.settings = None # Manually ensure settings is None for this test

                    with pytest.raises(RuntimeError, match="Settings not initialized"):
                        loader.get_settings()