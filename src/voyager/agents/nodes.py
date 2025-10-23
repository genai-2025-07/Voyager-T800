"""
LangGraph node functions for the Voyager T800 agent.

Each node represents a step in the agent's reasoning and action loop.
"""

import logging
import time
from typing import Literal

from src.voyager.utils.read_prompt_from_file import read_prompt_from_file
from langchain_core.messages import SystemMessage, ToolMessage, AIMessage, HumanMessage, RemoveMessage, BaseMessage
from langgraph.graph import END, MessagesState

from src.voyager.agents.tools import get_events, get_itineraries, get_weather_forecast
from src.voyager.models.llms.llm_factory import get_llm
from src.voyager.config.config import settings
from src.voyager.agents.memory.messages_filter import filter_conversation_messages
from src.voyager.agents.memory.token_counter import count_messages_tokens
from src.voyager.config.config import settings

logger = logging.getLogger(__name__)

# Initialize tools and LLM
tools = [get_weather_forecast, get_events, get_itineraries]
tools_by_name = {tool.name: tool for tool in tools}
llm = get_llm("claude")
llm_with_tools = llm.bind_tools(tools)


# System prompt for the agent
SYSTEM_PROMPT = read_prompt_from_file('src/voyager/prompts/agent_claude_prompt.txt')


def llm_call(state: MessagesState) -> dict:
    """
    Node that calls the LLM with tools bound.
    The LLM can either:
    - Generate a final response (text)
    - Request tool calls to gather more information
    
    When processing messages with images:
    - Images are treated as contextual input for travel preferences
    - The agent extracts destination hints, style preferences, or activity types
    - Images are NOT described in the output, only used to inform itinerary design
    
    Args:
        state: Current conversation state with messages
        
    Returns:
        Updated state with the LLM's response message
    """
    messages = [SystemMessage(content=SYSTEM_PROMPT)] + state["messages"]
    response = llm_with_tools.invoke(messages)
    return {"messages": [response]}


def tool_node(state: MessagesState) -> dict:
    """
    Node that executes tool calls requested by the LLM.
    
    Processes all tool calls from the last message and appends
    the results as ToolMessages to the conversation.
    
    Args:
        state: Current conversation state with messages
        
    Returns:
        Updated state with tool results appended
    """
    last_message = state["messages"][-1]
    results = []

    # The model might produce multiple tool calls
    for tool_call in last_message.tool_calls:
        tool_name = tool_call["name"]
        args = tool_call["args"]

        if tool_name not in tools_by_name:
            results.append(
                ToolMessage(
                    content=f"Error: unknown tool '{tool_name}'",
                    tool_call_id=tool_call["id"],
                )
            )
            continue

        tool = tools_by_name[tool_name]
        observation = tool.invoke(args)
        results.append(ToolMessage(content=str(observation), tool_call_id=tool_call["id"]))

    return {"messages": results}


def should_continue(state: MessagesState) -> Literal["tools", "summarize", "end"]:
    """
    Conditional edge function that determines next step.
    
    Priority order:
    1. If last message has tool calls: route to "tools" node
    2. If conversation needs summarization: route to "summarize" node
    3. Otherwise: route to END (conversation complete)
    
    Args:
        state: Current conversation state with messages
        
    Returns:
        Next node name: "tools", "summarize", or "end"
    """
    messages = state["messages"]
    last_message = messages[-1]
    
    if last_message.tool_calls:
        return "tools"
    
    if should_summarize(state):
        return "summarize"
    
    # Default: End conversation
    return "end"

def should_summarize(state: MessagesState) -> bool:
    """
    Determine if the conversation needs summarization.
    
    Only summarizes for authenticated users. Anonymous users should refresh
    the page when they hit token limits.
    
    Args:
        state: Current conversation state with messages
        
    Returns:
        True if summarization should be triggered (authenticated users only)
    """
    messages = state["messages"]
    
    conversation_messages = filter_conversation_messages(messages)
    
    token_count = count_messages_tokens(conversation_messages)
    token_threshold = settings.memory_token_soft_limit
    should_trigger = token_count > token_threshold
    
    if should_trigger:
        logger.info(
            f"Summarization triggered: {token_count} tokens in {len(conversation_messages)} conversation messages "
            f"(threshold: {token_threshold} tokens)"
        )
    
    return should_trigger


def format_messages_for_summary(messages: list[BaseMessage]) -> str:
    """
    Format messages into a readable string for the summarization prompt.
    
    Only includes conversation messages (user and assistant), skips tool calls.
    
    Args:
        messages: List of messages to format
        
    Returns:
        Formatted string with User/Assistant prefixes
    """
    formatted = []
    for msg in messages:
        if isinstance(msg, HumanMessage):
            # Handle both simple string content and multi-modal content (with images)
            if isinstance(msg.content, str):
                formatted.append(f"User: {msg.content}")
            elif isinstance(msg.content, list):
                # Extract text from multi-modal content
                text_parts = [
                    item.get("text", "") 
                    for item in msg.content 
                    if isinstance(item, dict) and item.get("type") == "text"
                ]
                if text_parts:
                    formatted.append(f"User: {' '.join(text_parts)}")
        elif isinstance(msg, AIMessage):
            # Skip tool call messages, only include final responses
            if not msg.tool_calls and msg.content:
                formatted.append(f"Assistant: {msg.content}")
    
    return "\n\n".join(formatted)


def summarize(state: MessagesState) -> dict:
    """
    Summarize old conversation messages to reduce context size.
    
    Strategy:
    1. Keep the N most recent messages intact
    2. Summarize all older messages into a single AI message
    3. Replace old messages with the summary message
    4. Use RemoveMessage to delete old messages from state
    
    This keeps context manageable while preserving conversation continuity.
    
    Args:
        state: Current conversation state with messages
        
    Returns:
        Updated state with summary message + recent messages
    """
    messages = state["messages"]
    keep_recent = settings.memory_keep_recent_messages  # e.g., 3
    
    logger.info(f"Starting summarization: {len(messages)} total messages, keeping last {keep_recent}")
    
    # Split messages into old (to summarize) and recent (to keep)
    if len(messages) <= keep_recent:
        # Not enough messages to summarize, shouldn't reach here
        logger.warning("Summarization triggered but not enough messages to summarize")
        return {"messages": []}
    
    messages_to_summarize = messages[:-keep_recent]
    recent_messages = messages[-keep_recent:]
    
    # Format old messages for the summarization prompt
    formatted_conversation = format_messages_for_summary(messages_to_summarize)
    
    # Create summarization prompt
    summary_template = read_prompt_from_file("src/voyager/prompts/conversation_summary_template.txt")
    summary_prompt = HumanMessage(content=summary_template.format(
        formatted_conversation=formatted_conversation
    ))
    
    # Get summary from LLM
    logger.info(f"Calling LLM to summarize {len(messages_to_summarize)} messages...")
    summary_response = llm.invoke([summary_prompt])
    
    # Count tokens in summarized messages for metadata
    from src.voyager.agents.memory.token_counter import count_messages_tokens
    summarized_token_count = count_messages_tokens(messages_to_summarize)
    
    # Create visible summary message that replaces old messages
    summary_message = AIMessage(
        content=f"📝 **Earlier Conversation Summary**\n\n{summary_response.content}",
        metadata={
            "is_summary": True,
            "summarized_count": len(messages_to_summarize),
            "summarized_tokens": summarized_token_count,
            "timestamp": time.time()
        }
    )
    
    # Delete ALL existing messages
    delete_all = [RemoveMessage(id=m.id) for m in messages]
    
    # Create FRESH copies of recent messages (without old IDs)
    # This is crucial - if we reuse the original message objects, LangGraph
    # maintains them by ID and won't respect our new ordering
    fresh_recent_messages = []
    for msg in recent_messages:
        if isinstance(msg, HumanMessage):
            fresh_recent_messages.append(HumanMessage(content=msg.content))
        elif isinstance(msg, AIMessage):
            fresh_recent_messages.append(AIMessage(content=msg.content))
    
    logger.info(
        f"Summarization complete: {len(messages_to_summarize)} messages ({summarized_token_count} tokens) → 1 summary message. "
        f"Keeping {len(recent_messages)} recent messages."
    )
    
    # Return: delete all existing, then add in desired order
    # delete_all removes everything, then we add: [summary] + [fresh recent messages]
    return {"messages": delete_all + [summary_message] + fresh_recent_messages}
