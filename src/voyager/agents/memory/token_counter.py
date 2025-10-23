"""
Token counting utilities using LangChain's built-in functionality.

This module provides token counting for context window management,
leveraging LangChain's model-specific token counting.
"""

import logging
from typing import List

from langchain_core.messages import BaseMessage

from src.voyager.models.llms.llm_factory import get_llm

logger = logging.getLogger(__name__)


def get_token_counter_llm():
    """
    Get LLM instance for token counting.
    
    Uses the same model as the agent for accurate counting.
    This ensures token counts match what the agent actually uses.
    
    Returns:
        LLM instance with token counting capabilities
    """
    # Use the same model that the agent uses for consistency
    # Default to "claude" as per agent configuration
    return get_llm("claude")


def count_messages_tokens(messages: List[BaseMessage]) -> int:
    """
    Count total tokens for a list of messages using LangChain's built-in method.
    
    This handles:
    - Text content
    - Multi-modal content (text + images)
    - Different message types (Human, AI, System, Tool)
    - Model-specific tokenization
    
    Args:
        messages: List of LangChain messages (HumanMessage, AIMessage, etc.)
        
    Returns:
        Total token count across all messages
    """
    if not messages:
        return 0
    
    try:
        llm = get_token_counter_llm()
        
        # LangChain's built-in method handles everything including images
        token_count = llm.get_num_tokens_from_messages(messages)
        
        logger.debug(f"Counted {token_count} tokens across {len(messages)} messages")
        return token_count
        
    except Exception as e:
        logger.warning(f"Error using LangChain token counting, falling back to estimate: {e}")
        # Fallback: rough estimate
        return estimate_tokens_fallback(messages)


def estimate_tokens_fallback(messages: List[BaseMessage]) -> int:
    """
    Fallback token estimation if built-in counting fails.
    
    Uses conservative estimates:
    - ~4 characters per token for text
    - ~1,500 tokens per image (after resize to 1024x1024)
    
    Args:
        messages: List of LangChain messages
        
    Returns:
        Estimated token count
    """
    total = 0
    
    for msg in messages:
        if isinstance(msg.content, str):
            # Simple text message
            total += len(msg.content) // 4
        elif isinstance(msg.content, list):
            # Multi-modal message (text + images)
            for item in msg.content:
                if isinstance(item, dict):
                    if item.get("type") == "text":
                        total += len(item.get("text", "")) // 4
                    elif item.get("type") == "image":
                        # Conservative estimate for resized images
                        total += 1500
    
    logger.debug(f"Estimated {total} tokens (fallback method)")
    return total


def count_checkpoint_tokens(checkpoint_messages: List[BaseMessage]) -> int:
    """
    Count tokens in messages from a LangGraph checkpoint.
    
    Filters out tool messages first (they're not sent to LLM in final context).
    
    Args:
        checkpoint_messages: Messages from LangGraph checkpoint state
        
    Returns:
        Token count for conversation messages only
    """
    from src.voyager.agents.memory.messages_filter import filter_conversation_messages
    
    # Filter to only conversation messages (remove tool calls)
    filtered = filter_conversation_messages(checkpoint_messages)
    
    return count_messages_tokens(filtered)


def check_single_message_limit(message: BaseMessage, hard_limit: int = None) -> tuple[int, bool]:
    """
    Check if a single message exceeds the hard limit.
    
    Used to reject messages that are too large on their own,
    regardless of conversation history.
    
    Args:
        message: Message to check
        hard_limit: Maximum allowed tokens (defaults to 180,000)
        
    Returns:
        (token_count, exceeds_limit)
    """
    if hard_limit is None:
        hard_limit = 180000  # Default hard limit for Claude
    
    token_count = count_messages_tokens([message])
    exceeds = token_count > hard_limit
    
    if exceeds:
        logger.warning(f"Single message exceeds hard limit: {token_count}/{hard_limit} tokens")
    
    return token_count, exceeds

