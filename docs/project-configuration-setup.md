### Instructions on Using the Config Loading Workflow

#### **1. Definition of the Base Configuration (`app/config/default.yaml`)**

Default settings are defined in `app/config/default.yaml`. This file should contain all the common settings that apply across most environments.

Example `app/config/default.yaml`:

```yaml
app:
  name: voyager-t800
  env: dev
  version: 0.1.0

model:
  openai:
    model_name: text-embedding-3-small
  groq:
    model_name: llama3-8b-8192

embedding:
  provider: openai
  max_tokens: 450

logging_config_file: null
```

#### **2. Environment-Specific Overrides (Optional)**

For different deployment environments (e.g., `dev`, `prod`), there are corresponding YAML files (e.g., `app/config/dev.yaml`, `app/config/prod.yaml`). These files only need to contain the settings that differ from `default.yaml`.
> **Important!**
>
> If some setting values is instance of list or set the override will completely replace the base (default) value.


Example `app/config/prod.yaml`:

```yaml
app:
  env: prod
  api_key: ${PROD_APP_API_KEY} # This will be expanded from an environment variable

model:
  openai:
    api_key: ${OPENAI_API_KEY} # This will be expanded from an environment variable

embedding:
  output_dir: data/embeddings/production
```

#### **3. Use Environment Variables for Sensitive Data and Dynamic Settings**

Environment variables are crucial for values that change between deployments or contain sensitive information (like API keys) that should not be committed to version control.

*   **For local development**: Create a `.env` file in your project root.

    Example `.env` file:

    ```
    APP_ENV=dev
    OPENAI_API_KEY=sk-your-dev-openai-key
    PROD_APP_API_KEY=sk-your-prod-app-key
    ```

*   **For deployment environments**: Set environment variables directly in your deployment platform (e.g., Kubernetes, Docker, CI/CD pipelines).

*   **Referencing in YAML**: Use the `${VAR_NAME}` syntax in your YAML files to reference environment variables. You can also provide a default value: `${VAR_NAME:default_value}`.

    Example (from `prod.yaml` above):
    `api_key: ${PROD_APP_API_KEY}`
    `url: ${API_URL:https://default.com}`

#### **4. Instantiating and Accessing Settings**


```python
from pathlib import Path
from app.config.loader import ConfigLoader
from app.config.config_models import Settings

# Option 1: Basic usage, relies on default.yaml and environment variables/APP_ENV
config_loader = ConfigLoader()
settings: Settings = config_loader.get_settings()

print(f"App Name: {settings.app.name}")
print(f"OpenAI Model: {settings.model.openai.model_name}")
print(f"Embedding Output Directory: {settings.embedding.output_dir}")

# Option 2: Explicitly provide an override config path
# For example, to load 'prod.yaml' explicitly:
# Make sure 'prod.yaml' exists in app/config or provide the full path
prod_config_path = Path(__file__).resolve().parents[1] / "config" / "prod.yaml"
prod_config_loader = ConfigLoader(config_path=str(prod_config_path))
prod_settings: Settings = prod_config_loader.get_settings()

print(f"\nProd App Name: {prod_settings.app.name}")
print(f"Prod OpenAI API Key: {prod_settings.model.openai.api_key}") # This would come from PROD_APP_API_KEY env var
```

#### **5. Adding New Application Feature Configuration (Pydantic Model)**

To introduce configuration for a new application feature, follow these steps:

1.  **Define the Pydantic Model in `app/config/config_models.py`**:
    Create a new class that inherits from `BaseConfigModel`. Define all configuration parameters for your new feature as class attributes with appropriate type hints, default values, and Pydantic `Field` validations.

    ```python
    # app/config/config_models.py

    class NewFeatureSettings(BaseConfigModel):
        enabled: bool = Field(default=False, description="Enable or disable the new feature.")
        threshold: float = Field(default=0.5, ge=0.0, le=1.0, description="A threshold value for the feature.")
        api_endpoint: Optional[str] = Field(default=None, description="API endpoint for the new feature.")
    ```

2.  **Integrate into the Main `Settings` Model**:
    Add an instance of your new feature's Pydantic model as a field in the main `Settings` class, using `default_factory` for proper initialization.

    ```python
    # app/config/config_models.py

    # ... other imports and classes

    class Settings(BaseConfigModel):
        app: AppSettings = Field(default_factory=AppSettings)
        model: ModelSettings = Field(default_factory=ModelSettings)
        embedding: EmbeddingSettings = Field(default_factory=EmbeddingSettings)
        vectordb: VectorDBSettings = Field(default_factory=VectorDBSettings)
        bedrock: BedrockSettings = Field(default_factory=BedrockSettings)
        attraction_parser: AttractionParserSettings = Field(default_factory=AttractionParserSettings)
        summary_memory: SummaryMemorySettings = Field(default_factory=SummaryMemorySettings)
        prompt: PromptSettings = Field(default_factory=PromptSettings)
        new_feature: NewFeatureSettings = Field(default_factory=NewFeatureSettings) # Add your new feature here
        logging_config_file: Optional[str] = Field(default=None)
    ```

3.  **Update `__all__` in `app/config/config_models.py`**:
    Add your new settings class to the `__all__` list to make it easily importable.

    ```python
    # app/config/config_models.py

    # ... other classes

    __all__ = [
        # ... existing settings classes
        "NewFeatureSettings", # Add your new settings class
        "Settings",
    ]
    ```

4.  **Add Default Configuration in `app/config/default.yaml`**:
    Provide default values for your new feature in the base `default.yaml` file. This is crucial for the `ConfigLoader` to recognize and load these settings.

    ```yaml
    # app/config/default.yaml

    # ... existing configurations

    new_feature:
      enabled: false
      threshold: 0.75
      api_endpoint: https://api.example.com/new-feature
    ```

Your new feature's configuration will now be automatically loaded, merged, expanded, and validated by the `ConfigLoader`, accessible via `settings.new_feature`.

#### **6. Handling Validation Errors**

Since Pydantic validation is strict (`extra="forbid"`), ensure your YAML files only contain keys defined in the `Settings` models. If you introduce an unknown key or a value with an incorrect type, a `pydantic.ValidationError` will be raised during `ConfigLoader` initialization, providing clear feedback on what went wrong.

**Troubleshooting Tips:**

*   **`FileNotFoundError`**: Double-check the paths to `default.yaml` and any override YAML files.
*   **`ValueError` (during env var expansion)**: Ensure all required environment variables referenced with `${VAR_NAME}` are set, or provide a default value using `${VAR_NAME:default_value}`.
*   **`pydantic.ValidationError`**: This is your guide to fixing schema mismatches. Read the error message carefully to identify which field is causing the problem (e.g., an extra field, an incorrect type, or a missing required field).
*   **Unexpected Configuration Values**: Verify the precedence order: explicit `config_path` > `VOYAGER_CONFIG` env var > `APP_ENV` based file > `default.yaml`. Also, remember `load_dotenv(override=False)` means system environment variables win over `.env` file entries if there's a conflict.