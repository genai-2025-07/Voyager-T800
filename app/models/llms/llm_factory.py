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

logger = logging.getLogger(__name__)
load_dotenv()


def get_llm(provider: Optional[str] = None) -> Union[ChatGroq, ChatOpenAI]:
    """
    Get an LLM instance from the specified provider.

    Args:
        provider: The LLM provider to use. If None, uses LLM_PROVIDER env var (default: "groq").
                 Supported providers: "groq", "openai"

    Returns:
        Union[ChatGroq, ChatOpenAI]: Configured LLM instance

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
        else:
            error_msg = f"Unsupported LLM provider: {provider}. Supported providers: groq, openai"
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
    print(api_key)
    if not api_key:
        error_msg = "GROQ_API_KEY environment variable is required for Groq provider"
        logger.error(error_msg)
        raise ValueError(error_msg)

    model_name = os.getenv("GROQ_MODEL_NAME", "llama3-8b-8192")
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
