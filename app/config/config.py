from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings."""

    app_name: str = Field(default='Voyager-T800')
    app_version: str = Field(default='0.1.0')
    app_description: str = Field(
        default='AI-powered travel planning assistant which helps users generate personalized itineraries by combining their travel preferences (text) and inspiration images'
    )

    app_env: str = Field(default='development')
    host: str = Field(default='127.0.0.1')
    port: int = Field(default=8000)
    debug: bool = Field(default=False)

    allowed_origins: list[str] = Field(default=['http://localhost:3000'])
    allowed_methods: list[str] = Field(default=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'])
    allowed_headers: list[str] = Field(default=['*'])

    logging_config_file: str = Field(default='logger.yaml')
    log_level: str = Field(default='INFO')
    service_name: str = Field(default='local-fastapi')

    model_config = SettingsConfigDict(
        env_file='../.env', env_file_encoding='utf-8', case_sensitive=False, extra='allow'
    )


settings = Settings()
