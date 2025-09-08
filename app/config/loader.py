from __future__ import annotations

import os
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict

import yaml
from dotenv import load_dotenv

from app.config.config_models import Settings


class ConfigLoader:
    """
    Loads, merges, expands, and validates YAML configuration files.

    This class provides a comprehensive configuration management system that:
    - Loads a base configuration from `default.yaml`
    - Merges with environment-specific overrides (dev.yaml, prod.yaml)
    - Expands environment variable placeholders (${VAR_NAME})
    - Validates the final configuration against Pydantic models

    Precedence for override path: explicit `config_path` argument > VOYAGER_CONFIG env var
    Default base file: app/config/default.yaml

    Attributes:
        project_root (Path): Root directory of the project
        config_dir (Path): Directory containing configuration files
        base_config_path (Path): Path to the default configuration file
        override_path (Path | None): Path to the override configuration file
        _raw_config (Dict[str, Any]): Raw configuration data before validation
        settings (Settings | None): Validated configuration settings
    """

    def __init__(self, project_root: str, config_path: str | None = None):
        """
        Initialize the ConfigLoader with optional override configuration path.

        Args:
            config_path (str | None): Path to override configuration file.
                If None, will check VOYAGER_CONFIG environment variable,
                then fall back to environment-based file (dev.yaml/prod.yaml)
                based on APP_ENV or app.env setting.
            project_root str: Path to project root.

        Raises:
            FileNotFoundError: If base configuration file is not found
            ValueError: If configuration files contain invalid YAML or structure
        """

        self.project_root = project_root
        self.config_dir = self.project_root / "app" / "config"
        self.base_config_path = self.config_dir / "default.yaml"
        # Load .env early to populate environment for expansion
        dotenv_path = os.path.join(self.project_root, '.env')
        load_dotenv(dotenv_path, override=False)

        env_override = os.getenv("VOYAGER_CONFIG")
        self.override_path = Path(config_path) if config_path else (Path(env_override) if env_override else None)

        self._raw_config: Dict[str, Any] = {}
        self.settings: Settings | None = None

        self._load_config()
        self._expand_env_vars()
        self._validate_and_expose()

    def _load_yaml_file(self, path: Path) -> Dict[str, Any]:
        """
        Load and parse a YAML configuration file.

        Args:
            path (Path): Path to the YAML configuration file.

        Returns:
            Dict[str, Any]: Parsed YAML data as a dictionary.

        Raises:
            FileNotFoundError: If the configuration file does not exist.
            ValueError: If the YAML file does not contain a top-level mapping (dict).
            yaml.YAMLError: If the YAML file contains invalid YAML syntax.
        """
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {path}")
        with path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
            if not isinstance(data, dict):
                raise ValueError(f"Config file must contain a mapping at top-level: {path}")
            return data

    def _load_config(self) -> None:
        """
        Load and merge configuration files.

        This method:
        1. Loads the base configuration from `default.yaml`
        2. Determines the override file path based on:
           - Explicit config_path argument
           - VOYAGER_CONFIG environment variable
           - APP_ENV environment variable or app.env setting
        3. Loads and merges the override configuration if it exists
        4. Stores the merged configuration in `_raw_config`

        The override file path is determined in this order:
        1. Explicit config_path argument to __init__
        2. VOYAGER_CONFIG environment variable
        3. Environment-based file (dev.yaml/prod.yaml) based on APP_ENV or app.env

        Raises:
            FileNotFoundError: If base configuration file is not found
            ValueError: If configuration files contain invalid structure
        """
        base = self._load_yaml_file(self.base_config_path)
        merged = deepcopy(base)

        if self.override_path is None:
            # Environment-based convenience: if APP_ENV is set to dev/prod, try that file
            app_env = os.getenv("APP_ENV") or base.get("app", {}).get("env")
            if app_env:
                candidate = self.config_dir / f"{app_env}.yaml"
                if candidate.exists():
                    self.override_path = candidate
                else:
                    raise FileNotFoundError(f"Config file not found: {candidate}")


        if self.override_path:
            override_data = self._load_yaml_file(self.override_path)
            merged = self._recursive_merge(merged, override_data)

        self._raw_config = merged

    def _recursive_merge(self, base_dict: Dict[str, Any], override_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Recursively merge two dictionaries, with override values taking precedence.

        This method performs a deep merge where:
        - If both values are dictionaries, they are recursively merged
        - If both values are lists, they are merged (extend)
        - If both values are sets, they are merged (union)
        - If the override value is not a dictionary/list/set, it completely replaces the base value
        - All values are deep-copied to avoid modifying the original dictionaries

        Args:
            base_dict (Dict[str, Any]): The base dictionary to merge into.
            override_dict (Dict[str, Any]): The override dictionary with values to merge.

        Returns:
            Dict[str, Any]: A new dictionary containing the merged result.

        Example:
            base = {"a": 1, "b": {"c": 2, "d": 3}}
            override = {"b": {"c": 4}, "e": 5}
            result = {"a": 1, "b": {"c": 4, "d": 3}, "e": 5}
        """
        result = deepcopy(base_dict)
        for key, override_value in (override_dict or {}).items():
            if key in result:
                base_value = result[key]
                if isinstance(base_value, dict) and isinstance(override_value, dict):
                    result[key] = self._recursive_merge(base_value, override_value)
                elif isinstance(base_value, list) and isinstance(override_value, list):
                    result[key].extend(deepcopy(override_value))
                elif isinstance(base_value, set) and isinstance(override_value, set):
                    result[key] = base_value.union(deepcopy(override_value))
                else:
                    result[key] = deepcopy(override_value)
            else:
                result[key] = deepcopy(override_value)
        return result

    def _expand_env_vars(self) -> None:
        """
        Recursively expand environment variable placeholders in the configuration.

        This method traverses the entire configuration structure and replaces
        environment variable placeholders (${VAR_NAME}) with their actual values
        from the environment. It supports both simple placeholders and those
        with default values (${VAR_NAME:default}).

        The expansion is done in-place on the `_raw_config` attribute.

        Raises:
            ValueError: If an environment variable placeholder references an
                       undefined variable without a default value.

        Example:
            Input: {"api_key": "${OPENAI_API_KEY}", "url": "${API_URL:https://default.com}"}
            Output: {"api_key": "sk-...", "url": "https://default.com"}
        """
        def expand(value: Any) -> Any:
            if isinstance(value, str):
                return self._expand_string(value)
            if isinstance(value, dict):
                return {k: expand(v) for k, v in value.items()}
            if isinstance(value, list):
                return [expand(v) for v in value]
            if isinstance(value, set):
                return {expand(v) for v in value}
            return value

        self._raw_config = expand(self._raw_config)

    def _expand_string(self, s: str) -> str:
        """
        Expand environment variable placeholders in a single string.

        This method parses a string and replaces environment variable placeholders
        with their corresponding values from the environment. It supports two formats:
        - Simple placeholder: ${VAR_NAME}
        - Placeholder with default: ${VAR_NAME:default_value}

        Args:
            s (str): The string containing environment variable placeholders.

        Returns:
            str: The string with all placeholders replaced by their values.

        Raises:
            ValueError: If a placeholder is malformed (unclosed braces) or references
                       an undefined environment variable without a default value.

        Examples:
            >>> _expand_string("${HOME}/config")
            "/home/user/config"
            >>> _expand_string("${API_URL:https://default.com}")
            "https://default.com"  # if API_URL is not set
            >>> _expand_string("${REQUIRED_VAR}")
            ValueError: Environment variable 'REQUIRED_VAR' is not defined...
        """
        # Support ${VAR} and default syntax ${VAR:default}
        result = ""
        i = 0
        while i < len(s):
            if s[i] == "$" and i + 1 < len(s) and s[i + 1] == "{":
                j = s.find("}", i + 2)
                if j == -1:
                    raise ValueError(f"Unclosed environment variable placeholder in: {s[i+2:i+5]}")
                placeholder = s[i + 2 : j]
                if ":" in placeholder:
                    var_name, default_val = placeholder.split(":", 1)
                else:
                    var_name, default_val = placeholder, None
                var_name = var_name.strip()
                env_val = os.getenv(var_name)
                if env_val is None:
                    if (default_val is None or default_val == ""):
                        raise ValueError(f"Environment variable {var_name} not set")
                    if default_val is not None:
                        env_val = default_val
                    else:
                        raise ValueError(f"Environment variable '{var_name}' is not defined for placeholder ${{{placeholder}}}")
                result += env_val
                i = j + 1
            else:
                result += s[i]
                i += 1
        return result

    def _validate_and_expose(self) -> None:
        """
        Validate the configuration data and create the Settings instance.

        This method instantiates the Pydantic Settings model with the merged
        and expanded configuration data. The Pydantic model will automatically
        validate all fields according to their type annotations and field constraints.

        The validated settings are stored in the `settings` attribute for later use.

        Raises:
            pydantic.ValidationError: If the configuration data does not match
                                     the expected schema or field constraints.
        """
        self.settings = Settings(**self._raw_config)

    def get_settings(self) -> Settings:
        """
        Get the validated configuration settings.

        Returns:
            Settings: The validated configuration settings instance.

        Raises:
            RuntimeError: If the settings have not been initialized (e.g., if
                         configuration loading failed).

        Example:
            >>> loader = ConfigLoader()
            >>> settings = loader.get_settings()
            >>> print(settings.app.name)
            "voyager-t800"
        """
        if self.settings is None:
            raise RuntimeError("Settings not initialized")
        return self.settings


__all__ = ["ConfigLoader"]


