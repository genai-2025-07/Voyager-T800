from typing import Dict, Any
import os
import yaml
import re

class FallbackMapping:
    def __init__(self, values: Dict[str, Any], fallbacks: Dict[str, str]):
        self.values = values
        self.fallbacks = fallbacks

    def __getitem__(self, key: str) -> str:
        if key in self.values:
            return str(self.values[key])
        
        if key in self.fallbacks:
            return self.fallbacks[key]
        
        return f'[missing: {key}]'

class PromptManager:
    """
    Manages prompt templates for the Voyager T800 travel planning system.
    
    This class handles loading, formatting, and managing prompt templates from
    text files. It provides robust error handling for missing files and template
    variables, with intelligent fallback values for common template placeholders.
    
    Attributes:
        prompts_dir (Path): Directory containing prompt template files
    """
    
    def __init__(self):
        """
        Initialize the PromptManager with a prompts directory.
        
        The prompts directory path is loaded from a YAML configuration file
        specified by the MAP_DATA_CONFIG_PATH environment variable.
        
        Raises:
            ValueError: If MAP_DATA_CONFIG_PATH environment variable is not set
            FileNotFoundError: If the configuration file doesn't exist
            yaml.YAMLError: If the configuration file contains invalid YAML
            KeyError: If the 'prompts_dir' key is missing from the configuration
            RuntimeError: If the prompts directory doesn't exist or is not accessible
        """
        self.config_dict = self._load_config_file()
        self.prompts_dir = self._extract_prompts_dir()
        self.fallback_values = self._extract_fallback_values()

    def _get_config_path(self) -> str:
        config_path = os.getenv('MAP_DATA_CONFIG_PATH')
        if not config_path:
            raise ValueError(
                "MAP_DATA_CONFIG_PATH environment variable is not set. "
                "Please set it to the path of your configuration file."
            )
        return config_path

    def _load_config_file(self) -> dict:
        config_path = self._get_config_path()
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config_dict = yaml.safe_load(f)
        except FileNotFoundError:
            raise FileNotFoundError(
                f"Configuration file not found: {config_path}\n"
                f"Please ensure the file exists and MAP_DATA_CONFIG_PATH points to the correct location."
            )
        except yaml.YAMLError as e:
            raise yaml.YAMLError(
                f"Invalid YAML in configuration file {config_path}: {e}\n"
                f"Please check the YAML syntax."
            )
        except Exception as e:
            raise RuntimeError(
                f"Unexpected error reading configuration file {config_path}: {e}"
            )
        
        if not isinstance(config_dict, dict):
            raise ValueError(
                f"Configuration file {config_path} must contain a YAML dictionary, "
                f"got {type(config_dict).__name__}"
            )
        
        return config_dict

    def _extract_prompts_dir(self) -> str:
        if 'prompts_dir' not in self.config_dict:
            raise KeyError(
                f"Configuration file is missing required key 'prompts_dir'.\n"
                f"Available keys: {list(self.config_dict.keys())}"
            )
        
        prompts_dir_path = self.config_dict['prompts_dir']
        if not isinstance(prompts_dir_path, str):
            raise ValueError(
                f"Configuration key 'prompts_dir' must be a string, "
                f"got {type(prompts_dir_path).__name__}"
            )
        
        if not prompts_dir_path.strip():
            raise ValueError(
                "Configuration key 'prompts_dir' cannot be empty or whitespace-only"
            )
        
        return self._validate_prompts_directory(prompts_dir_path)

    def _validate_prompts_directory(self, prompts_dir_path: str):
        try:
            from pathlib import Path
            prompts_dir = Path(prompts_dir_path).resolve()
            
            if not prompts_dir.exists():
                raise FileNotFoundError(
                    f"Prompts directory does not exist: {prompts_dir}\n"
                    f"Please ensure the directory exists or update the configuration."
                )
            
            if not prompts_dir.is_dir():
                raise NotADirectoryError(
                    f"Prompts path is not a directory: {prompts_dir}\n"
                    f"Please ensure the path points to a directory, not a file."
                )
            
            return prompts_dir
                
        except Exception as e:
            raise RuntimeError(
                f"Failed to validate prompts directory {prompts_dir_path}: {e}"
            )

    def load_prompt(self, name: str) -> str:
        """
        Load a prompt template from a text file.
        
        This method reads a prompt template file from the prompts directory.
        The file should be named '{name}.txt' and contain the template text
        with placeholders for dynamic values.
        
        Args:
            name: The name of the prompt template file (without .txt extension)
            
        Returns:
            str: The contents of the prompt template file
            
        Raises:
            ValueError: If the name contains invalid characters or path traversal attempts
            FileNotFoundError: If the prompt template file doesn't exist
            UnicodeDecodeError: If the file contains invalid UTF-8 characters
        """
        sanitized_name = self._sanitize_filename(name)
        
        template_path = self.prompts_dir / f"{sanitized_name}.txt"
        try:
            resolved_path = template_path.resolve()
            if not str(resolved_path).startswith(str(self.prompts_dir.resolve())):
                raise ValueError(
                    f"Path traversal attempt detected. Requested path would resolve outside "
                    f"the prompts directory: {resolved_path}"
                )
        except (RuntimeError, OSError) as e:
            raise ValueError(f"Invalid path: {e}")
        
        if not template_path.exists():
            raise FileNotFoundError(f"Prompt template '{name}' not found at {template_path}")
        
        return template_path.read_text(encoding="utf-8")

    def _sanitize_filename(self, name: str) -> str:

        if not name or not name.strip():
            raise ValueError("Filename cannot be empty or whitespace-only")
        
        name = name.strip()
        
        dangerous_patterns = [
            '..', '../', '..\\', '..\\\\',
            '/', '\\',
            '~',
            ':',
        ]
        
        for pattern in dangerous_patterns:
            if pattern in name:
                raise ValueError(
                    f"Filename contains dangerous pattern '{pattern}' that could lead to path traversal. "
                    f"Only alphanumeric characters, hyphens, and underscores are allowed."
                )
        
        if not re.match(r'^[a-zA-Z0-9_-]+$', name):
            raise ValueError(
                f"Filename contains invalid characters. Only alphanumeric characters, "
                f"hyphens (-), and underscores (_) are allowed. Got: '{name}'"
            )
        
        if len(name) > 100:
            raise ValueError(f"Filename too long. Maximum length is 100 characters. Got: {len(name)}")
        
        return name
    
    def format_prompt(self, template: str, values: Dict[str, Any]) -> str:
        """
        Format a prompt template with provided values, handling missing keys gracefully.
        
        This method formats a template string by replacing placeholders with values
        from the provided dictionary. It handles missing keys by using fallback values
        or leaving the placeholder as-is, preventing KeyError exceptions.
        
        Args:
            template: The template string containing placeholders like {city}, {days}
            values: Dictionary of values to substitute into the template
            
        Returns:
            str: The formatted prompt with all available values substituted
            
        Raises:
            ValueError: If template is None or empty
            TypeError: If values is not a dictionary
        """
        if template is None:
            raise ValueError("Template cannot be None")
        
        if not isinstance(template, str):
            raise TypeError(f"Template must be a string, got {type(template).__name__}")
        
        if not template.strip():
            raise ValueError("Template cannot be empty or whitespace-only")
        
        if not isinstance(values, dict):
            raise TypeError(f"Values must be a dictionary, got {type(values).__name__}")
        
        fallback_mapping = FallbackMapping(values, self.fallback_values)
        
        return template.format_map(fallback_mapping)

    def _extract_fallback_values(self) -> Dict[str, str]:
        if 'fallback_values' not in self.config_dict:
            raise KeyError("Configuration file is missing required key 'fallback_values'.")
        
        fallback_values = self.config_dict['fallback_values']
        if not isinstance(fallback_values, dict):
            raise ValueError(
                f"Configuration key 'fallback_values' must be a dictionary, "
                f"got {type(fallback_values).__name__}"
            )
        
        for key, value in fallback_values.items():
            if not isinstance(value, str):
                raise ValueError(
                    f"Fallback value for key '{key}' must be a string, "
                    f"got {type(value).__name__}"
                )
        
        return fallback_values
    
    def get_formatted_prompt(self, name: str, values: Dict[str, Any]) -> str:
        """
        Load and format a prompt template with provided values.
        
        This method combines loading a prompt template and formatting it with
        the provided values. It includes comprehensive error handling for both
        loading and formatting operations, returning error messages instead of
        raising exceptions.
        
        Args:
            name: The name of the prompt template file (without .txt extension)
            values: Dictionary of values to substitute into the template
            
        Returns:
            str: The formatted prompt, or an error message if loading/formatting fails
        """
        try:
            template = self.load_prompt(name)
        except Exception as e:
            return f"[PromptManager Error] Failed to load prompt '{name}': {str(e)}"
        try:
            return self.format_prompt(template, values)
        except Exception as e:
            return f"[PromptManager Error] Failed to format prompt '{name}': {str(e)}"
    
    def list_available_prompts(self) -> list:
        """
        List all available prompt template files.
        
        This method scans the prompts directory for .txt files and returns
        a list of their names without the .txt extension.
        
        Returns:
            list: List of available prompt template names
        """
        prompt_files = list(self.prompts_dir.glob("*.txt"))
        return [f.stem for f in prompt_files]