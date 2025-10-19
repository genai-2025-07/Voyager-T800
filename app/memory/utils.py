
"""Shared utilities for memory and checkpointing."""

from typing import Sequence
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage
import functools
from typing import Any
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import Checkpoint, CheckpointMetadata, ChannelVersions


def filter_conversation_messages(messages: Sequence[BaseMessage]) -> list[BaseMessage]:
    """
    Filter message list to keep only clean user/assistant conversation.
    
    Removes:
    - ToolMessage instances (tool results)
    - AIMessage instances with tool_calls (tool invocations)
    
    Keeps:
    - HumanMessage (user input)
    - AIMessage without tool_calls (final responses)

    Note: 
    - FOR FILTERING CHANGES BOTH FOR ANON AND USER SESSIONS USE THIS FUNCTION
    """
    filtered = []
    for msg in messages:
        if isinstance(msg, HumanMessage):
            filtered.append(msg)
        elif isinstance(msg, AIMessage):
            if not msg.tool_calls and not hasattr(msg, 'tool_calls'):
                filtered.append(msg)
            elif hasattr(msg, 'tool_calls') and len(msg.tool_calls) == 0:
                filtered.append(msg)
        elif isinstance(msg, ToolMessage):
            continue
    return filtered


def make_filtering_checkpointer(base_checkpointer):
    """
    Wrap any checkpointer to filter messages before saving.
    
    This allows us to apply message filtering to any checkpointer type
    (MemorySaver, DynamoDBSaver, etc.) without subclassing.
    
    Args:
        base_checkpointer: Any checkpointer instance (MemorySaver, etc.)
        
    Returns:
        The same checkpointer instance with filtered put() method
    """
    original_put = base_checkpointer.put
    
    @functools.wraps(original_put)
    def filtered_put(
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        """Filter messages in checkpoint before saving."""
        if 'messages' in checkpoint.get('channel_values', {}):
            original_messages = checkpoint['channel_values']['messages']
            filtered_messages = filter_conversation_messages(original_messages)
            checkpoint['channel_values']['messages'] = filtered_messages
        
        return original_put(config, checkpoint, metadata, new_versions)
    
    # Replace the put method
    base_checkpointer.put = filtered_put
    return base_checkpointer


