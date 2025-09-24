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

    # Frontend (Streamlit) Configuration
    streamlit_env: str = Field(default='dev', description='Environment for Streamlit UI')
    voyager_page_title: str = Field(default='Voyager-T800 Travel Assistant')
    voyager_page_icon: str = Field(default='🚀')
    voyager_page_tagline: str = Field(default='*Your AI-powered conversational trip planner*')
    voyager_max_input_length: int = Field(default=500)
    voyager_sessions_page_size: int = Field(default=10)
    image_display_width: int = Field(default=400)

    # DynamoDB Configuration
    use_local_dynamodb: bool = Field(default=False, description='Use local DynamoDB instead of AWS')
    dynamodb_endpoint_url: str = Field(default='http://localhost:8003', description='Local DynamoDB endpoint URL')
    dynamodb_table: str = Field(default='session_metadata', description='DynamoDB table name')
    aws_region: str = Field(default='us-east-2', description='AWS region for DynamoDB')
    aws_access_key_id: str | None = Field(default='dummy', description='AWS access key ID')
    aws_secret_access_key: str | None = Field(default='dummy', description='AWS secret access key')

    logging_config_file: str = Field(default='logger.yaml')
    log_level: str = Field(default='INFO')
    service_name: str = Field(default='local-fastapi')

    # Weaviate Configuration
    weaviate_host: str = Field(default='localhost', description='Weaviate host')
    weaviate_port: int = Field(default=8090, description='Weaviate HTTP port')
    weaviate_grpc_host: str = Field(default='localhost', description='Weaviate gRPC host')
    weaviate_grpc_port: int = Field(default=50051, description='Weaviate gRPC port')
    weaviate_http_secure: bool = Field(default=False, description='Use HTTPS for Weaviate HTTP')
    weaviate_grpc_secure: bool = Field(default=False, description='Use TLS for Weaviate gRPC')

    # LLM / Chain Configuration
    groq_api_key: str | None = Field(default=None)
    groq_model_name: str = Field(default='llama3-8b-8192')
    groq_temperature: float = Field(default=0.7)
    session_memory_max_token_limit: int = Field(default=1000)
    session_memory_ttl_seconds: int = Field(default=3600)

    model_config = SettingsConfigDict(
        env_file='../.env', env_file_encoding='utf-8', case_sensitive=False, extra='allow'
    )


settings = Settings()
