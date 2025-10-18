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

from app.agents.graph import create_agent
from app.config.config import settings

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
checkpointer = MemorySaver()

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
            if is_authenticated:
                # Lazy-init DynamoDB checkpointer if needed
                if dynamodb_checkpointer is None:
                    logger.info("Initializing DynamoDB checkpointer...")
                    
                    if settings.use_local_dynamodb:
                        dynamodb_checkpointer = DynamoDBSaver(
                            table_name=settings.dynamodb_table,
                            region_name=settings.aws_region,
                            endpoint_url=settings.dynamodb_endpoint_url,
                            aws_access_key_id=settings.aws_access_key_id,
                            aws_secret_access_key=settings.aws_secret_access_key,
                        )
                        logger.info("DynamoDB checkpointer initialized (local)")
                    else:
                        dynamodb_checkpointer = DynamoDBSaver(
                            table_name=settings.dynamodb_table,
                            region_name=settings.aws_region,
                        )
                        logger.info("DynamoDB checkpointer initialized (AWS)")
                
                # Compile agent with DynamoDB checkpointer if needed
                if agent_graph_dynamodb is None:
                    agent_graph_dynamodb = create_agent(checkpointer=dynamodb_checkpointer)
                    logger.info('LangGraph agent with DynamoDB checkpointer initialized')
                
                return agent_graph_dynamodb
            else:
                # Compile agent with MemorySaver if needed
                if agent_graph_memory is None:
                    agent_graph_memory = create_agent(checkpointer=memory_checkpointer)
                    logger.info('LangGraph agent with MemorySaver initialized')
                
                return agent_graph_memory


def stream_response(
    user_input: str,
    session_id: str = "default_session",
    image_base64: Optional[str] = None,  # Changed from image_urls
    image_media_type: str = "image/jpeg"  # Default media type
):
    """
    Stream the agent's response token-by-token for real-time display.
    
    Args:
        user_input: User's text query
        session_id: Unique session identifier
        image_base64: Optional base64-encoded image string (without data:image prefix)
        image_media_type: Media type of the image (e.g., "image/jpeg", "image/png", "image/webp")
    """
    agent = initialize_agent()
    history_messages = get_session_state(session_id)
    full_response_text = "" 
    config = {"configurable": {"thread_id": session_id}}
    
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
    
    try:
        for message_chunk, metadata in agent.stream(
            {"messages": [user_message]},
            config=config,
            stream_mode="messages"
        ):
            node_name = metadata.get("langgraph_node", "")
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
        logger.info(f"Streaming completed {len(full_response_text)} chars).")
            
    except Exception as e:
        logger.error(f"Agent streaming failed: {e}", exc_info=True)
        raise


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

