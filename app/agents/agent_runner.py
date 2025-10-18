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

from app.memory.dynamodb_checkpointer import DynamoDBSaver
from app.memory.utils import make_filtering_checkpointer
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langgraph.checkpoint.memory import MemorySaver

from app.agents.graph import create_agent
from app.config.config import settings

logger = logging.getLogger(__name__)


memory_checkpointer = make_filtering_checkpointer(MemorySaver())
agent_graph_memory = None
agent_graph_dynamodb = None
dynamodb_checkpointer = None
agent_lock = Lock()

 
 
def initialize_agent(user_id: Optional[str] = None):
    """
    Initialize the LangGraph agent (compiled graph).
    
    Thread-safe lazy initialization to avoid creating the agent at import time.
    The agent includes tool binding and the execution graph.
    
    Returns:
        Compiled LangGraph agent ready for invocation
    """
    global agent_graph_memory, agent_graph_dynamodb, dynamodb_checkpointer
    is_authenticated = user_id and not user_id.startswith("anon_")
    
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
    session_id: str,
    user_id: str = None,
):
    """
    Stream the agent's response token-by-token for real-time display.
    Avoids double LLM calls by capturing final state directly from stream metadata.
    """

    agent = initialize_agent(user_id)

    if user_id and not user_id.startswith("anon"):
        thread_id = f"{user_id}-{session_id}"
    else:
        thread_id = session_id
    
    config = {"configurable": {"thread_id": thread_id}}



    # history_messages = get_session_state(session_id)
    full_response_text = "" 
    config = {"configurable": {"thread_id": session_id}}

    user_message = HumanMessage(content=user_input)
 
    try:
        # --- Single streaming loop ---
        for message_chunk, metadata in agent.stream(
            {"messages": [user_message]},
            config=config,
            stream_mode="messages"
        ):
            node_name = metadata.get("langgraph_node", "")

            if node_name == "llm_call" and message_chunk.content:
                chunk_text = message_chunk.content
                if isinstance(chunk_text, str):
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

