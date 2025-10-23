"""
LLM Factory module for creating language model instances from different providers.

This module provides a unified interface for creating LLM instances from various
providers (OpenAI, Bedrock/Claude) using the application's configuration
(rather than explicitly loading a .env file here).
"""

import os
import logging
from typing import Optional, Union, Any

from langchain_openai import ChatOpenAI
from langchain_aws import ChatBedrock

# Prefer the application's Settings instance (pydantic) as the configuration source.
# Fall back to os.environ only when the Settings object doesn't have the value.
from voyager.config.config import settings

logger = logging.getLogger(__name__)


def _get_config(key: str, default: Any = None) -> Any:
    """
    Helper to fetch configuration values.

    Priority:
     1. attribute on the `settings` object (case-insensitive)
     2. direct environment variable (os.environ)
     3. provided default

    This keeps configuration centralized in pydantic Settings while allowing environment
    fallbacks where necessary.
    """
    # Try several attribute name casings on the settings object
    for attr in (key, key.lower(), key.upper()):
        if hasattr(settings, attr):
            val = getattr(settings, attr)
            # Accept False / 0 / "" as valid values; treat None as missing
            if val is not None:
                return val

    # fallback to environment variables
    return os.environ.get(key, default)


def get_llm(provider: Optional[str] = None) -> Union[ChatOpenAI, ChatBedrock]:
    """
    Get an LLM instance from the specified provider.

    Args:
        provider: The LLM provider to use. If None, uses LLM_PROVIDER from config/env.
                  Supported providers: , "openai", "claude" (bedrock)

    Returns:
        Configured LLM instance

    Raises:
        ValueError: If provider is not supported or required configuration is missing
        RuntimeError: If LLM initialization fails
    """
    provider = (provider or _get_config("LLM_PROVIDER", "claude")).lower()
    logger.info(f"Initializing LLM with provider: {provider}")

    try:
        if provider == "openai":
            return _create_openai_llm()
        elif provider == "claude" or provider == "bedrock":
            return _create_claude_llm()
        else:
            error_msg = f"Unsupported LLM provider: {provider}. Supported providers: openai, claude"
            logger.error(error_msg)
            raise ValueError(error_msg)

    except Exception as e:
        logger.error(f"Failed to initialize LLM with provider '{provider}': {str(e)}")
        raise RuntimeError(f"LLM initialization failed: {str(e)}") from e


def _create_openai_llm() -> ChatOpenAI:
    """
    Create and configure an OpenAI LLM instance.

    Uses configuration from the settings object first, then environment variables.
    """
    api_key = _get_config("OPENAI_API_KEY")
    if not api_key:
        error_msg = "OPENAI_API_KEY is required for OpenAI provider (check config or environment)"
        logger.error(error_msg)
        raise ValueError(error_msg)

    model_name = _get_config("OPENAI_MODEL_NAME", "gpt-4o-mini")
    temperature_raw = _get_config("OPENAI_TEMPERATURE", "0.7")
    try:
        temperature = float(temperature_raw)
    except Exception:
        logger.warning("OPENAI_TEMPERATURE invalid, defaulting to 0.7")
        temperature = 0.7

    logger.info(f"Creating OpenAI LLM with model: {model_name}, temperature: {temperature}")

    try:
        return ChatOpenAI(api_key=api_key, model=model_name, temperature=temperature, streaming=True)
    except Exception as e:
        logger.error(f"Failed to create OpenAI LLM instance: {str(e)}")
        raise


def _create_claude_llm() -> ChatBedrock:
    """
    Create and configure a Claude LLM instance accessed via AWS Bedrock.

    Configuration is taken from settings (preferred) or env vars as fallback:
      - BEDROCK_MODEL_ID / CLAUDE_MODEL_ID
      - BEDROCK_TEMPERATURE / CLAUDE_TEMPERATURE
      - BEDROCK_MAX_TOKENS / CLAUDE_MAX_TOKENS
      - BEDROCK_READ_TIMEOUT, BEDROCK_CONNECT_TIMEOUT
      - AWS credentials from settings.aws_* or env vars
    """
    # region: prefer settings.aws_region, fallback to AWS_REGION env var or default
    region = _get_config("aws_region", _get_config("AWS_REGION", "us-east-2"))

    # model id: check common names
    model_id = _get_config("CLAUDE_MODEL_ID", _get_config("BEDROCK_MODEL_ID",
                                                          "us.anthropic.claude-sonnet-4-5-20250929-v1:0"))

    temperature_raw = _get_config("CLAUDE_TEMPERATURE", _get_config("BEDROCK_TEMPERATURE", "0.7"))
    try:
        temperature = float(temperature_raw)
    except Exception:
        logger.warning("CLAUDE/BEDROCK temperature invalid, defaulting to 0.7")
        temperature = 0.7

    max_tokens_raw = _get_config("CLAUDE_MAX_TOKENS", _get_config("BEDROCK_MAX_TOKENS", "8192"))
    try:
        max_tokens = int(max_tokens_raw)
    except Exception:
        logger.warning("CLAUDE/BEDROCK max_tokens invalid, defaulting to 8192")
        max_tokens = 8192

    read_timeout = int(_get_config("BEDROCK_READ_TIMEOUT", 300))
    connect_timeout = int(_get_config("BEDROCK_CONNECT_TIMEOUT", 10))

    logger.info(
        f"Creating Claude LLM via Bedrock with model: {model_id}, region: {region}, "
        f"temperature: {temperature}, timeouts: connect={connect_timeout}s, read={read_timeout}s"
    )

    try:
        import boto3
        from botocore.config import Config

        bedrock_config = Config(
            region_name=region,
            read_timeout=read_timeout,
            connect_timeout=connect_timeout,
            retries={"max_attempts": 3, "mode": "adaptive"},
        )

        # If explicit credentials are present on settings or env, pass them to client
        aws_access_key_id = _get_config("aws_access_key_id", _get_config("AWS_ACCESS_KEY_ID"))
        aws_secret_access_key = _get_config("aws_secret_access_key", _get_config("AWS_SECRET_ACCESS_KEY"))
        aws_session_token = _get_config("aws_session_token", _get_config("AWS_SESSION_TOKEN"))

        client_kwargs = {"service_name": "bedrock-runtime", "region_name": region, "config": bedrock_config}
        if aws_access_key_id and aws_secret_access_key:
            client_kwargs.update(
                {
                    "aws_access_key_id": aws_access_key_id,
                    "aws_secret_access_key": aws_secret_access_key,
                }
            )
        if aws_session_token:
            client_kwargs["aws_session_token"] = aws_session_token

        bedrock_client = boto3.client(**client_kwargs)

        return ChatBedrock(
            model_id=model_id,
            client=bedrock_client,
            model_kwargs={"temperature": temperature, "max_tokens": max_tokens},
        )
    except Exception as e:
        logger.error(f"Failed to create Claude/Bedrock LLM instance: {str(e)}")
        raise

