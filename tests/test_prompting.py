import pytest
import os
import tempfile
import yaml
from pathlib import Path
from unittest.mock import patch, mock_open, MagicMock
from app.models.llms.basic_workflow.prompting import PromptManager, FallbackMapping


class TestFallbackMapping:
    """Tests for the FallbackMapping class."""
    
    def test_getitem_with_existing_key(self):
        """Test getting a value that exists in the values dictionary."""
        values = {"city": "Kyiv", "days": 5}
        fallbacks = {"country": "Ukraine"}
        mapping = FallbackMapping(values, fallbacks)
        
        assert mapping["city"] == "Kyiv"
        assert mapping["days"] == "5"  # Should be converted to string
    
    def test_getitem_with_fallback_key(self):
        """Test getting a value that exists in the fallbacks dictionary."""
        values = {"city": "Kyiv"}
        fallbacks = {"country": "Ukraine", "currency": "UAH"}
        mapping = FallbackMapping(values, fallbacks)
        
        assert mapping["country"] == "Ukraine"
        assert mapping["currency"] == "UAH"
    
    def test_getitem_with_missing_key(self):
        """Test getting a value that doesn't exist in either dictionary."""
        values = {"city": "Kyiv"}
        fallbacks = {"country": "Ukraine"}
        mapping = FallbackMapping(values, fallbacks)
        
        assert mapping["missing_key"] == "[missing: missing_key]"
    
    def test_getitem_prioritizes_values_over_fallbacks(self):
        """Test that values dictionary takes priority over fallbacks."""
        values = {"city": "Kyiv"}
        fallbacks = {"city": "Lviv"}  # Same key in both
        mapping = FallbackMapping(values, fallbacks)
        
        assert mapping["city"] == "Kyiv"  # Should use values, not fallbacks


class TestPromptManager:
    """Tests for the PromptManager class."""
    
    @pytest.fixture
    def mock_config(self):
        """Create a mock configuration dictionary."""
        return {
            "prompts_dir": "/tmp/test_prompts",
            "fallback_values": {
                "city": "Unknown City",
                "days": "Unknown Days",
                "country": "Unknown Country"
            }
        }
    
    @pytest.fixture
    def temp_prompts_dir(self):
        """Create a temporary prompts directory for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            prompts_dir = Path(temp_dir) / "prompts"
            prompts_dir.mkdir()
            
            # Create some test prompt files
            (prompts_dir / "test_prompt.txt").write_text("Hello {city}!")
            (prompts_dir / "complex_prompt.txt").write_text(
                "Visit {city} in {country} for {days} days"
            )
            
            yield prompts_dir
    
    @pytest.fixture
    def temp_config_file(self, mock_config, temp_prompts_dir):
        """Create a temporary configuration file."""
        mock_config["prompts_dir"] = str(temp_prompts_dir)
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(mock_config, f)
            config_path = f.name
        
        yield config_path
        
        # Cleanup
        os.unlink(config_path)
    
    def test_init_success(self, temp_config_file):
        """Test successful initialization of PromptManager."""
        with patch.dict(os.environ, {'MAP_DATA_CONFIG_PATH': temp_config_file}):
            pm = PromptManager()
            assert pm.prompts_dir is not None
            assert pm.fallback_values is not None
    
    def test_init_missing_env_var(self):
        """Test initialization fails when MAP_DATA_CONFIG_PATH is not set."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="MAP_DATA_CONFIG_PATH environment variable is not set"):
                PromptManager()
    
    def test_init_config_file_not_found(self):
        """Test initialization fails when config file doesn't exist."""
        with patch.dict(os.environ, {'MAP_DATA_CONFIG_PATH': '/nonexistent/file.yaml'}):
            with pytest.raises(FileNotFoundError, match="Configuration file not found"):
                PromptManager()
    
    def test_init_invalid_yaml(self):
        """Test initialization fails with invalid YAML."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("invalid: yaml: content: [")
            config_path = f.name
        
        try:
            with patch.dict(os.environ, {'MAP_DATA_CONFIG_PATH': config_path}):
                with pytest.raises(yaml.YAMLError):
                    PromptManager()
        finally:
            os.unlink(config_path)
    
    def test_init_missing_prompts_dir_key(self):
        """Test initialization fails when prompts_dir key is missing."""
        config = {"fallback_values": {"city": "Unknown"}}
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config, f)
            config_path = f.name
        
        try:
            with patch.dict(os.environ, {'MAP_DATA_CONFIG_PATH': config_path}):
                with pytest.raises(KeyError, match="Configuration file is missing required key 'prompts_dir'"):
                    PromptManager()
        finally:
            os.unlink(config_path)
    
    def test_init_prompts_dir_not_string(self):
        """Test initialization fails when prompts_dir is not a string."""
        config = {
            "prompts_dir": 123,  # Should be string
            "fallback_values": {"city": "Unknown"}
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config, f)
            config_path = f.name
        
        try:
            with patch.dict(os.environ, {'MAP_DATA_CONFIG_PATH': config_path}):
                with pytest.raises(ValueError, match="Configuration key 'prompts_dir' must be a string"):
                    PromptManager()
        finally:
            os.unlink(config_path)
    
    def test_init_prompts_dir_empty(self):
        """Test initialization fails when prompts_dir is empty."""
        config = {
            "prompts_dir": "",  # Empty string
            "fallback_values": {"city": "Unknown"}
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config, f)
            config_path = f.name
        
        try:
            with patch.dict(os.environ, {'MAP_DATA_CONFIG_PATH': config_path}):
                with pytest.raises(ValueError, match="Configuration key 'prompts_dir' cannot be empty"):
                    PromptManager()
        finally:
            os.unlink(config_path)
    
    def test_init_prompts_dir_not_exists(self):
        """Test initialization fails when prompts directory doesn't exist."""
        config = {
            "prompts_dir": "/nonexistent/directory",
            "fallback_values": {"city": "Unknown"}
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config, f)
            config_path = f.name
        
        try:
            with patch.dict(os.environ, {'MAP_DATA_CONFIG_PATH': config_path}):
                with pytest.raises(RuntimeError, match="Failed to validate prompts directory"):
                    PromptManager()
        finally:
            os.unlink(config_path)
    
    def test_load_prompt_success(self, temp_config_file):
        """Test successful loading of a prompt template."""
        with patch.dict(os.environ, {'MAP_DATA_CONFIG_PATH': temp_config_file}):
            pm = PromptManager()
            template = pm.load_prompt("test_prompt")
            assert template == "Hello {city}!"
    
    def test_load_prompt_not_found(self, temp_config_file):
        """Test loading a non-existent prompt template."""
        with patch.dict(os.environ, {'MAP_DATA_CONFIG_PATH': temp_config_file}):
            pm = PromptManager()
            with pytest.raises(FileNotFoundError, match="Prompt template 'nonexistent' not found"):
                pm.load_prompt("nonexistent")
    
    def test_load_prompt_path_traversal_attempt(self, temp_config_file):
        """Test that path traversal attempts are blocked."""
        with patch.dict(os.environ, {'MAP_DATA_CONFIG_PATH': temp_config_file}):
            pm = PromptManager()
            with pytest.raises(ValueError, match="Filename contains dangerous pattern"):
                pm.load_prompt("../../../etc/passwd")
    
    def test_load_prompt_dangerous_patterns(self, temp_config_file):
        """Test that dangerous filename patterns are rejected."""
        with patch.dict(os.environ, {'MAP_DATA_CONFIG_PATH': temp_config_file}):
            pm = PromptManager()
            
            dangerous_names = [
                "test..txt",
                "test/../file",
                "test\\file",
                "~/.bashrc",
                "file:name"
            ]
            
            for name in dangerous_names:
                with pytest.raises(ValueError, match="Filename contains dangerous pattern"):
                    pm.load_prompt(name)
    
    def test_load_prompt_invalid_characters(self, temp_config_file):
        """Test that filenames with invalid characters are rejected."""
        with patch.dict(os.environ, {'MAP_DATA_CONFIG_PATH': temp_config_file}):
            pm = PromptManager()
            
            invalid_names = [
                "test@file",
                "test#file",
                "test$file",
                "test%file",
                "test&file"
            ]
            
            for name in invalid_names:
                with pytest.raises(ValueError, match="Filename contains invalid characters"):
                    pm.load_prompt(name)
    
    def test_load_prompt_empty_name(self, temp_config_file):
        """Test that empty filenames are rejected."""
        with patch.dict(os.environ, {'MAP_DATA_CONFIG_PATH': temp_config_file}):
            pm = PromptManager()
            
            with pytest.raises(ValueError, match="Filename cannot be empty"):
                pm.load_prompt("")
            
            with pytest.raises(ValueError, match="Filename cannot be empty"):
                pm.load_prompt("   ")
    
    def test_load_prompt_too_long(self, temp_config_file):
        """Test that overly long filenames are rejected."""
        with patch.dict(os.environ, {'MAP_DATA_CONFIG_PATH': temp_config_file}):
            pm = PromptManager()
            long_name = "a" * 101  # 101 characters, over the 100 limit
            
            with pytest.raises(ValueError, match="Filename too long"):
                pm.load_prompt(long_name)
    
    def test_format_prompt_success(self, temp_config_file):
        """Test successful formatting of a prompt template."""
        with patch.dict(os.environ, {'MAP_DATA_CONFIG_PATH': temp_config_file}):
            pm = PromptManager()
            template = "Hello {city}! Visit {country} for {days} days."
            values = {"city": "Kyiv", "country": "Ukraine", "days": 5}
            
            result = pm.format_prompt(template, values)
            assert result == "Hello Kyiv! Visit Ukraine for 5 days."
    
    def test_format_prompt_with_fallbacks(self, temp_config_file):
        """Test formatting with fallback values for missing keys."""
        with patch.dict(os.environ, {'MAP_DATA_CONFIG_PATH': temp_config_file}):
            pm = PromptManager()
            template = "Hello {city}! Visit {country} for {days} days."
            values = {"city": "Kyiv"}  # Missing country and days
            
            result = pm.format_prompt(template, values)
            assert result == "Hello Kyiv! Visit Unknown Country for Unknown Days days."
    
    def test_format_prompt_with_missing_keys(self, temp_config_file):
        """Test formatting with keys that have no fallbacks."""
        with patch.dict(os.environ, {'MAP_DATA_CONFIG_PATH': temp_config_file}):
            pm = PromptManager()
            template = "Hello {city}! Visit {unknown_place}."
            values = {"city": "Kyiv"}
            
            result = pm.format_prompt(template, values)
            assert result == "Hello Kyiv! Visit [missing: unknown_place]."
    
    def test_format_prompt_none_template(self, temp_config_file):
        """Test formatting with None template."""
        with patch.dict(os.environ, {'MAP_DATA_CONFIG_PATH': temp_config_file}):
            pm = PromptManager()
            with pytest.raises(ValueError, match="Template cannot be None"):
                pm.format_prompt(None, {"city": "Kyiv"})
    
    def test_format_prompt_empty_template(self, temp_config_file):
        """Test formatting with empty template."""
        with patch.dict(os.environ, {'MAP_DATA_CONFIG_PATH': temp_config_file}):
            pm = PromptManager()
            with pytest.raises(ValueError, match="Template cannot be empty"):
                pm.format_prompt("", {"city": "Kyiv"})
            
            with pytest.raises(ValueError, match="Template cannot be empty"):
                pm.format_prompt("   ", {"city": "Kyiv"})
    
    def test_format_prompt_wrong_template_type(self, temp_config_file):
        """Test formatting with wrong template type."""
        with patch.dict(os.environ, {'MAP_DATA_CONFIG_PATH': temp_config_file}):
            pm = PromptManager()
            with pytest.raises(TypeError, match="Template must be a string"):
                pm.format_prompt(123, {"city": "Kyiv"})
    
    def test_format_prompt_wrong_values_type(self, temp_config_file):
        """Test formatting with wrong values type."""
        with patch.dict(os.environ, {'MAP_DATA_CONFIG_PATH': temp_config_file}):
            pm = PromptManager()
            with pytest.raises(TypeError, match="Values must be a dictionary"):
                pm.format_prompt("Hello {city}!", "not a dict")
    
    def test_get_formatted_prompt_success(self, temp_config_file):
        """Test successful loading and formatting of a prompt."""
        with patch.dict(os.environ, {'MAP_DATA_CONFIG_PATH': temp_config_file}):
            pm = PromptManager()
            values = {"city": "Kyiv", "country": "Ukraine", "days": 5}
            
            result = pm.get_formatted_prompt("complex_prompt", values)
            assert result == "Visit Kyiv in Ukraine for 5 days"
    
    def test_get_formatted_prompt_load_error(self, temp_config_file):
        """Test handling of prompt loading errors."""
        with patch.dict(os.environ, {'MAP_DATA_CONFIG_PATH': temp_config_file}):
            pm = PromptManager()
            values = {"city": "Kyiv"}
            
            result = pm.get_formatted_prompt("nonexistent", values)
            assert result.startswith("[PromptManager Error] Failed to load prompt")
    
    def test_get_formatted_prompt_format_error(self, temp_config_file):
        """Test handling of prompt formatting errors."""
        with patch.dict(os.environ, {'MAP_DATA_CONFIG_PATH': temp_config_file}):
            pm = PromptManager()
            
            # Create a prompt file with invalid format
            prompt_file = pm.prompts_dir / "invalid_prompt.txt"
            prompt_file.write_text("Hello {city}! {invalid_format}")
            
            result = pm.get_formatted_prompt("invalid_prompt", {"city": "Kyiv"})
            # The format should actually work with fallback mapping, so we test for success
            assert result == "Hello Kyiv! [missing: invalid_format]"
    
    def test_list_available_prompts(self, temp_config_file):
        """Test listing available prompt templates."""
        with patch.dict(os.environ, {'MAP_DATA_CONFIG_PATH': temp_config_file}):
            pm = PromptManager()
            
            # Create additional prompt files
            (pm.prompts_dir / "another_prompt.txt").write_text("Another template")
            (pm.prompts_dir / "third_prompt.txt").write_text("Third template")
            
            available_prompts = pm.list_available_prompts()
            expected = {"test_prompt", "complex_prompt", "another_prompt", "third_prompt"}
            assert set(available_prompts) == expected
    
    def test_list_available_prompts_empty_directory(self):
        """Test listing prompts in an empty directory."""
        # Create empty prompts directory
        with tempfile.TemporaryDirectory() as temp_dir:
            prompts_dir = Path(temp_dir) / "prompts"
            prompts_dir.mkdir()
            
            config = {
                "prompts_dir": str(prompts_dir),
                "fallback_values": {"city": "Unknown"}
            }
            
            with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
                yaml.dump(config, f)
                config_path = f.name
            
            try:
                with patch.dict(os.environ, {'MAP_DATA_CONFIG_PATH': config_path}):
                    pm = PromptManager()
                    available_prompts = pm.list_available_prompts()
                    assert available_prompts == []
            finally:
                os.unlink(config_path)
    
    def test_missing_fallback_values_key(self):
        """Test initialization fails when fallback_values key is missing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            prompts_dir = Path(temp_dir) / "prompts"
            prompts_dir.mkdir()
            
            config = {
                "prompts_dir": str(prompts_dir)
                # Missing fallback_values key
            }
            
            with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
                yaml.dump(config, f)
                config_path = f.name
            
            try:
                with patch.dict(os.environ, {'MAP_DATA_CONFIG_PATH': config_path}):
                    with pytest.raises(KeyError, match="Configuration file is missing required key 'fallback_values'"):
                        PromptManager()
            finally:
                os.unlink(config_path)
    
    def test_fallback_values_not_dict(self):
        """Test initialization fails when fallback_values is not a dictionary."""
        with tempfile.TemporaryDirectory() as temp_dir:
            prompts_dir = Path(temp_dir) / "prompts"
            prompts_dir.mkdir()
            
            config = {
                "prompts_dir": str(prompts_dir),
                "fallback_values": "not a dict"  # Should be dict
            }
            
            with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
                yaml.dump(config, f)
                config_path = f.name
            
            try:
                with patch.dict(os.environ, {'MAP_DATA_CONFIG_PATH': config_path}):
                    with pytest.raises(ValueError, match="Configuration key 'fallback_values' must be a dictionary"):
                        PromptManager()
            finally:
                os.unlink(config_path)
    
    def test_fallback_values_not_strings(self):
        """Test initialization fails when fallback values are not strings."""
        with tempfile.TemporaryDirectory() as temp_dir:
            prompts_dir = Path(temp_dir) / "prompts"
            prompts_dir.mkdir()
            
            config = {
                "prompts_dir": str(prompts_dir),
                "fallback_values": {
                    "city": "Unknown City",
                    "days": 123  # Should be string
                }
            }
            
            with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
                yaml.dump(config, f)
                config_path = f.name
            
            try:
                with patch.dict(os.environ, {'MAP_DATA_CONFIG_PATH': config_path}):
                    with pytest.raises(ValueError, match="Fallback value for key 'days' must be a string"):
                        PromptManager()
            finally:
                os.unlink(config_path)
