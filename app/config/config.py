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

    allowed_origins: list[str] = Field(
        default=['http://localhost:3000', 'http://localhost:8501', 'http://streamlit:8501']
    )
    allowed_methods: list[str] = Field(default=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'])
    allowed_headers: list[str] = Field(default=['*'])

    api_base_url: str = Field(default='http://localhost:8000')

    # DynamoDB Configuration
    use_local_dynamodb: bool = Field(default=False, description='Use local DynamoDB instead of AWS')
    dynamodb_endpoint_url: str = Field(default='http://localhost:8003', description='Local DynamoDB endpoint URL')
    dynamodb_table: str = Field(default='session_metadata', description='DynamoDB table name')
    aws_region: str = Field(default='us-east-2', description='AWS region for DynamoDB')
    aws_access_key_id: str | None = Field(default=None, description='AWS access key ID')
    aws_secret_access_key: str | None = Field(default=None, description='AWS secret access key')

    logging_config_file: str = Field(default='logger.yaml')
    log_level: str = Field(default='INFO')
    service_name: str = Field(default='local-fastapi')

    model_config = SettingsConfigDict(
        env_file='../.env', env_file_encoding='utf-8', case_sensitive=False, extra='allow'
    )


settings = Settings()
