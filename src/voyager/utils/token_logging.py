"""
Token usage logging utilities for monitoring and debugging.

This module provides functions for logging token usage during agent execution,
helping with debugging and monitoring token consumption patterns.
"""

import logging
from typing import List

from langchain_core.messages import BaseMessage

from src.voyager.agents.memory.token_counter import count_messages_tokens
from src.voyager.config.config import settings

logger = logging.getLogger(__name__)


def log_token_usage(messages: List[BaseMessage], session_id: str, phase: str):
    """
    Log token usage for debugging and monitoring.
    
    Args:
        messages: List of messages to count tokens for
        session_id: Session identifier for logging
        phase: Phase of execution (e.g., "before_stream", "after_stream")
    """
    try:
        from src.voyager.agents.memory.messages_filter import filter_conversation_messages
        
        # Count conversation tokens (filtered)
        conversation_messages = filter_conversation_messages(messages)
        conversation_tokens = count_messages_tokens(conversation_messages)
        
        # Count full tokens (unfiltered)
        full_tokens = count_messages_tokens(messages)
        
        # Calculate percentages
        soft_limit = settings.memory_token_soft_limit
        hard_limit = settings.memory_token_hard_limit
        
        conversation_percent = (conversation_tokens / soft_limit) * 100
        full_percent = (full_tokens / soft_limit) * 100
        
        # Determine status
        status = ""
        if full_tokens > hard_limit:
            status = " - EXCEEDS HARD LIMIT"
        elif full_tokens > soft_limit:
            status = " - EXCEEDS SOFT LIMIT - SUMMARIZATION RECOMMENDED"
        
        # Log the token usage
        logger.info(
            f"Token usage for session {session_id} ({phase}): "
            f"{full_tokens:,} tokens total ({conversation_tokens:,} conversation + {full_tokens - conversation_tokens:,} tools/system) "
            f"({full_percent:.1f}% of soft limit) - {len(messages)} total messages ({len(conversation_messages)} conversation){status}"
        )
        
    except Exception as e:
        logger.warning(f"Failed to log token usage: {e}")


def log_summarization_trigger(token_count: int, message_count: int, threshold: int):
    """
    Log when summarization is triggered.
    
    Args:
        token_count: Number of tokens in conversation messages
        message_count: Number of conversation messages
        threshold: Token threshold that was exceeded
    """
    logger.info(
        f"Summarization triggered: {token_count:,} tokens in {message_count} conversation messages "
        f"(threshold: {threshold:,} tokens)"
    )


def log_summarization_complete(summarized_count: int, summarized_tokens: int, kept_count: int):
    """
    Log when summarization is completed.
    
    Args:
        summarized_count: Number of messages that were summarized
        summarized_tokens: Number of tokens that were summarized
        kept_count: Number of recent messages that were kept
    """
    logger.info(
        f"Summarization complete: {summarized_count} messages ({summarized_tokens:,} tokens) → 1 summary message. "
        f"Keeping {kept_count} recent messages."
    )
