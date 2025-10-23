"""
Agent runner for Voyager T800 LangGraph agent.

This module provides the execution interface for the LangGraph agent,
replacing the chain-based approach with an agentic tool-calling system.
It uses MessagesState for clean, standardized session memory management.
"""

import logging
import time
from threading import Lock
from typing import Optional

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langgraph.checkpoint.memory import MemorySaver

from src.voyager.agents.graph import create_agent
from src.voyager.agents.memory.messages_filter import make_filtering_checkpointer
from src.voyager.config.config import settings
from src.voyager.agents.cancellation_manager  import get_cancellation_manager
from src.voyager.utils.token_logging import log_token_usage
logger = logging.getLogger(__name__)


# Memory configuration
SESSION_MEMORY_TTL_SECONDS = settings.session_memory_ttl_seconds

# Global agent - compiled once for efficiency
agent_graph = None
agent_lock = Lock()

# Session state dict: session_id -> {'messages': list[BaseMessage], 'last_access': timestamp}
# This directly stores LangGraph-compatible messages
session_states = {}
global checkpointer
checkpointer = make_filtering_checkpointer(MemorySaver())

def initialize_agent():
    """
    Initialize the LangGraph agent (compiled graph).
    
    Thread-safe lazy initialization to avoid creating the agent at import time.
    The agent includes tool binding and the execution graph.
    
    Returns:
        Compiled LangGraph agent ready for invocation
    """
    global agent_graph
    with agent_lock:
        if agent_graph is None:
            agent_graph = create_agent(checkpointer=checkpointer)
            logger.info('LangGraph agent initialized successfully')
    return agent_graph


def _cleanup_expired_sessions():
    """
    Remove session states that have not been accessed within TTL to avoid memory leaks.
    
    No-op if TTL is non-positive. Runs before each session state access to keep
    the memory footprint bounded.
    """
    try:
        ttl = SESSION_MEMORY_TTL_SECONDS
        if ttl <= 0:
            return

        now = time.time()
        expired_session_ids = []
        for s_id, entry in list(session_states.items()):
            if not isinstance(entry, dict) or 'last_access' not in entry:
                logger.warning(f'Malformed session entry for {s_id}: {entry}')
                continue
            if now - entry['last_access'] > ttl:
                expired_session_ids.append(s_id)
        
        for s_id in expired_session_ids:
            del session_states[s_id]
            logger.info(f'Expired session {s_id} cleaned up')
            
    except Exception as e:
        logger.warning(f'Session cleanup failed: {e}')


def get_session_state(session_id: str) -> list[BaseMessage]:
    """
    Get or initialize message state for a session.
    
    Returns a list of messages that is directly compatible with MessagesState.
    This is the clean, LangGraph-native way to manage conversation history.
    
    Args:
        session_id: Unique session identifier
        
    Returns:
        list[BaseMessage]: List of conversation messages for this session
    """
    _cleanup_expired_sessions()

    entry = session_states.get(session_id)

    if entry is not None and not isinstance(entry, dict):
        raise TypeError(f'Session state entry must be a dict, got type: {type(entry)}')

    if entry is None:
        # Create new session with empty message list
        session_states[session_id] = {
            'messages': [],
            'last_access': time.time()
        }
        logger.info(f'Initialized new session state for session_id: {session_id}')
        return session_states[session_id]['messages']

    # Update last access time (throttled to avoid excessive updates)
    if time.time() - entry['last_access'] > 10:
        entry['last_access'] = time.time()
    
    return entry['messages']


def save_session_state(session_id: str, messages: list[BaseMessage]):
    """
    Save the message state for a session.
    
    Updates the session's message list with the full conversation history.
    
    Args:
        session_id: Unique session identifier
        messages: Complete list of messages to save
    """
    _cleanup_expired_sessions()
    
    if session_id not in session_states:
        session_states[session_id] = {
            'messages': messages,
            'last_access': time.time()
        }
    else:
        session_states[session_id]['messages'] = messages
        session_states[session_id]['last_access'] = time.time()


def clear_session_state(session_id: str) -> bool:
    """
    Clear the in-memory session state for a session.
    
    Used for deleting anonymous sessions that are not persisted to DynamoDB.
    
    Args:
        session_id: Unique session identifier
        
    Returns:
        bool: True if session existed and was cleared, False if session didn't exist
    """
    if session_id in session_states:
        del session_states[session_id]
        logger.info(f'Cleared in-memory session state for session_id: {session_id}')
        return True
    return False


def stream_response(
    user_input: str,
    session_id: str = "default_session",
    image_base64: Optional[str] = None,
    image_media_type: str = "image/jpeg"
):
    """
    Stream the agent's response token-by-token with cancellation support.
    
    Args:
        user_input: User's text query
        session_id: Unique session identifier
        image_base64: Optional base64-encoded image string
        image_media_type: Media type of the image
        
    Raises:
        GenerationCancelledException: If generation is cancelled mid-stream
    """
    agent = initialize_agent()
    history_messages = get_session_state(session_id)
    full_response_text = "" 
    config = {"configurable": {"thread_id": session_id}}
    
    # Get cancellation manager
    cancellation_mgr = get_cancellation_manager()
    
    # Clear any previous cancellation flags for this session
    cancellation_mgr.clear(session_id)
    
    if image_base64:
        content = [
            {"type": "text", "text": user_input},
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": image_media_type,
                    "data": image_base64,
                }
            }
        ]
        user_message = HumanMessage(content=content)
    else:
        user_message = HumanMessage(content=user_input)
    
    input_messages = history_messages + [user_message]
    
    # Log token usage before streaming
    log_token_usage(input_messages, session_id, "before_stream")
    
    try:
        for message_chunk, metadata in agent.stream(
            {"messages": input_messages},
            config=config,
            stream_mode="messages"
        ):
            # Check for cancellation before processing each chunk
            if cancellation_mgr.is_cancelled(session_id):
                logger.info(f"Generation cancelled for session {session_id}")
                cancellation_mgr.clear(session_id)
                raise GenerationCancelledException(
                    f"Generation cancelled by user for session {session_id}"
                )
            
            node_name = metadata.get("langgraph_node", "")
            
            # Check if summarization node was executed
            if node_name == "summarize":
                # Yield a special marker to indicate summarization occurred
                yield "__SUMMARIZATION_OCCURRED__"
            
            if node_name == "llm_call" and message_chunk.content:
                chunk_text = message_chunk.content
                if isinstance(chunk_text, str):
                    full_response_text += chunk_text
                    yield chunk_text
                elif isinstance(chunk_text, list):
                    for item in chunk_text:
                        if isinstance(item, dict) and "text" in item:
                            full_response_text += item["text"]
                            yield item["text"]
                        elif isinstance(item, str):
                            full_response_text += item
                            yield item
        
        logger.info(f"Streaming completed ({len(full_response_text)} chars).")
        final_state = agent.get_state(config)
        if final_state and "messages" in final_state.values:
            # Log token usage after streaming
            log_token_usage(final_state.values["messages"], session_id, "after_stream")
            save_session_state(session_id, final_state.values["messages"])
            
    except GenerationCancelledException:
        # Re-raise cancellation exceptions
        raise
    except Exception as e:
        logger.error(f"Agent streaming failed: {e}", exc_info=True)
        raise
    finally:
        # Always clear cancellation flag when done
        cancellation_mgr.clear(session_id)


class GenerationCancelledException(Exception):
    """Exception raised when generation is cancelled by the user."""
    pass

def full_response(
    user_input: str, 
    session_id: str = 'default_session',
    image_base64: Optional[str] = None,  # Changed from image_urls
    image_media_type: str = "image/jpeg"
) -> str:
    """
    Get the complete agent response without streaming.
    
    Args:
        user_input: User's current request/query
        session_id: Unique session identifier for state isolation
        image_base64: Optional base64-encoded image string (without data:image prefix)
        image_media_type: Media type of the image (e.g., "image/jpeg", "image/png", "image/webp")
        
    Returns:
        Complete response string
    """
    agent = initialize_agent()
    history_messages = get_session_state(session_id)
    
    try:
        if image_base64:
            content = [
                {"type": "text", "text": user_input},
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": image_media_type,
                        "data": image_base64,
                    }
                }
            ]
            user_message = HumanMessage(content=content)
        else:
            user_message = HumanMessage(content=user_input)
        
        input_messages = history_messages + [user_message]
        result = agent.invoke({"messages": input_messages})
        
        final_message = result["messages"][-1]
        response = final_message.content if hasattr(final_message, 'content') else str(final_message)
        
        save_session_state(session_id, result["messages"])
        
        print(response, end='', flush=True)
        return response
        
    except Exception as e:
        logger.error(f'Agent invocation failed: {e}', exc_info=True)
        raise


def main():
    """
    CLI interface for testing the agent.
    
    Provides an interactive REPL for developers to test the agent's
    tool-calling and response generation without the frontend.
    """
    print('\n🤖 Voyager T800 Agent - Interactive Mode')
    print('=' * 50)
    print('The agent can call tools for weather, events, and itineraries.')
    print("Type 'q' to quit\n")

    session_id = 'cli_session'
    
    try:
        while True:
            user_input = input("\n💬 Your request: ")
            
            if user_input.lower() == 'q':
                print('\n👋 Goodbye!')
                break
            
            if not user_input.strip():
                continue
            
            print('\n🔄 Agent thinking...\n')
            print('📄 Response:\n')
            
            # Stream the response
            for chunk in stream_response(user_input, session_id):
                print(chunk, end='', flush=True)
            print('\n')
            
    except KeyboardInterrupt:
        print('\n\n👋 Session interrupted. Goodbye!')
        logger.info('User interrupted the session.')
    except Exception as e:
        print(f'\n❌ Error: {e}')
        logger.error(f'CLI error: {e}', exc_info=True)


if __name__ == '__main__':
    main()

