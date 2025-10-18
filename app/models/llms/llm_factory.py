"""
LLM Factory module for creating language model instances from different providers.

This module provides a unified interface for creating LLM instances from various
providers (Groq, OpenAI) with proper error handling and logging.
"""

import os
import logging
from typing import Optional, Union
from dotenv import load_dotenv

from langchain_groq import ChatGroq
from langchain_openai import ChatOpenAI
from langchain_aws import ChatBedrock

logger = logging.getLogger(__name__)
load_dotenv()


def get_llm(provider: Optional[str] = None) -> Union[ChatGroq, ChatOpenAI, ChatBedrock]:
    """
    Get an LLM instance from the specified provider.

    Args:
        provider: The LLM provider to use. If None, uses LLM_PROVIDER env var (default: "groq").
                 Supported providers: "groq", "openai", "claude"

    Returns:
        Union[ChatGroq, ChatOpenAI, ChatBedrock]: Configured LLM instance

    Raises:
        ValueError: If provider is not supported or required environment variables are missing
        RuntimeError: If LLM initialization fails
    """
    provider = provider or os.getenv("LLM_PROVIDER", "groq").lower()
    logger.info(f"Initializing LLM with provider: {provider}")

    try:
        if provider == "groq":
            return _create_groq_llm()
        elif provider == "openai":
            return _create_openai_llm()
        elif provider == "claude":
            return _create_claude_llm()
        else:
            error_msg = f"Unsupported LLM provider: {provider}. Supported providers: groq, openai, claude"
            logger.error(error_msg)
            raise ValueError(error_msg)

    except Exception as e:
        logger.error(f"Failed to initialize LLM with provider '{provider}': {str(e)}")
        raise RuntimeError(f"LLM initialization failed: {str(e)}") from e


def _create_groq_llm() -> ChatGroq:
    """
    Create and configure a Groq LLM instance.

    Returns:
        ChatGroq: Configured Groq LLM instance

    Raises:
        ValueError: If required environment variables are missing
    """
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        error_msg = "GROQ_API_KEY environment variable is required for Groq provider"
        logger.error(error_msg)
        raise ValueError(error_msg)

    model_name = os.getenv("GROQ_MODEL_NAME", "llama-3.1-8b-instant")
    temperature = float(os.getenv("GROQ_TEMPERATURE", "0.5"))

    logger.info(
        f"Creating Groq LLM with model: {model_name}, temperature: {temperature}"
    )

    try:
        return ChatGroq(
            groq_api_key=api_key,
            model=model_name,
            temperature=temperature,
            streaming=True,
        )
    except Exception as e:
        logger.error(f"Failed to create Groq LLM instance: {str(e)}")
        raise


def _create_openai_llm() -> ChatOpenAI:
    """
    Create and configure an OpenAI LLM instance.

    Returns:
        ChatOpenAI: Configured OpenAI LLM instance

    Raises:
        ValueError: If required environment variables are missing
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        error_msg = (
            "OPENAI_API_KEY environment variable is required for OpenAI provider"
        )
        logger.error(error_msg)
        raise ValueError(error_msg)

    model_name = os.getenv("OPENAI_MODEL_NAME", "gpt-4o-mini")
    temperature = float(os.getenv("OPENAI_TEMPERATURE", "0.7"))

    logger.info(
        f"Creating OpenAI LLM with model: {model_name}, temperature: {temperature}"
    )

    try:
        return ChatOpenAI(
            api_key=api_key, model=model_name, temperature=temperature, streaming=True
        )
    except Exception as e:
        logger.error(f"Failed to create OpenAI LLM instance: {str(e)}")
        raise


def _create_claude_llm() -> ChatBedrock:
    """
    Create and configure a Claude LLM instance via AWS Bedrock.
    Returns:
        ChatBedrock: Configured Claude LLM instance
    Raises:
        ValueError: If required environment variables are missing
    """
    # AWS credentials can be loaded from environment or AWS config
    region = "us-east-2"
    # Claude Sonnet 4.5 requires inference profile ARN, not direct model ID
    # Use cross-region inference profile for automatic failover
    model_id = os.getenv(
        "CLAUDE_MODEL_ID",
        "us.anthropic.claude-sonnet-4-5-20250929-v1:0"  # Cross-region inference profile
    )
    temperature = float(os.getenv("CLAUDE_TEMPERATURE", "0.7"))
    max_tokens = int(os.getenv("CLAUDE_MAX_TOKENS", "8192"))  # Increased for vision
    # Timeout settings for Bedrock requests (in seconds)
    # Vision/multimodal requests can take longer than text-only
    read_timeout = int(os.getenv("BEDROCK_READ_TIMEOUT", "300"))  # 5 minutes default
    connect_timeout = int(os.getenv("BEDROCK_CONNECT_TIMEOUT", "10"))
    
    logger.info(
        f"Creating Claude LLM via Bedrock with model: {model_id}, "
        f"region: {region}, temperature: {temperature}, "
        f"timeouts: connect={connect_timeout}s, read={read_timeout}s"
    )
    
    try:
        import boto3
        from botocore.config import Config
        
        # Configure boto3 client with custom timeouts
        bedrock_config = Config(
            region_name=region,
            read_timeout=read_timeout,
            connect_timeout=connect_timeout,
            retries={
                'max_attempts': 3,
                'mode': 'adaptive'
            }
        )
        
        # Create custom bedrock-runtime client
        bedrock_client = boto3.client(
            service_name="bedrock-runtime",
            region_name=region,
            config=bedrock_config
        )
        
        return ChatBedrock(
            model_id=model_id,
            client=bedrock_client,
            model_kwargs={
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
        )
    except Exception as e:
        logger.error(f"Failed to create Claude LLM instance: {str(e)}")
        raise 
