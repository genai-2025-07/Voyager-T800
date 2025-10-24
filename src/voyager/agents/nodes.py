"""
LangGraph node functions for the Voyager T800 agent.

Each node represents a step in the agent's reasoning and action loop.
"""

from typing import Literal
import logging

from src.voyager.utils.read_prompt_from_file import read_prompt_from_file
from langchain_core.messages import SystemMessage, ToolMessage
from langgraph.graph import END, MessagesState

from src.voyager.agents.tools import get_events, get_itineraries, get_weather_forecast
from src.voyager.models.llms.llm_factory import get_llm
from src.voyager.agents.budget_tracker import get_budget_tracker, BudgetExceededError

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
    
    BUDGET ENFORCEMENT: Increments paid_calls counter and checks timeout.
    
    Args:
        state: Current conversation state with messages
        
    Returns:
        Updated state with the LLM's response message
        
    Raises:
        BudgetExceededError: If budget limits exceeded
    """
    messages = [SystemMessage(content=SYSTEM_PROMPT)] + state["messages"]
    
    # Get budget tracker from state metadata
    config = state.get("__metadata__", {}).get("config", {})
    session_id = config.get("configurable", {}).get("thread_id", "default_session")
    
    # Get or create budget tracker (initialized in runner.py)
    from src.voyager.config.guardrails import guardrails_settings
    tracker = get_budget_tracker(
        session_id=session_id,
        max_tool_calls=guardrails_settings.MAX_TOOL_CALLS,
        max_paid_calls=guardrails_settings.MAX_PAID_CALLS,
        per_call_timeout=guardrails_settings.PER_CALL_TIMEOUT
    )
    
    # Check timeout before making call
    tracker.check_timeout()
    
    # Increment paid call counter
    tracker.increment_paid_call()
    
    response = llm_with_tools.invoke(messages)
    
    logger.info(f"LLM call completed. Budget: {tracker.get_stats()}")
    
    return {"messages": [response]}


def tool_node(state: MessagesState) -> dict:
    """
    Node that executes tool calls requested by the LLM.
    
    BUDGET ENFORCEMENT: Increments tool_calls counter for each tool invocation.
    
    Args:
        state: Current conversation state with messages
        
    Returns:
        Updated state with tool results appended
        
    Raises:
        BudgetExceededError: If tool call budget exceeded
    """
    last_message = state["messages"][-1]
    results = [] 
    
    # The model might produce multiple tool calls

    # Get budget tracker
    config = state.get("__metadata__", {}).get("config", {})
    session_id = config.get("configurable", {}).get("thread_id", "default_session")
    
    from src.voyager.config.guardrails import guardrails_settings
    tracker = get_budget_tracker(
        session_id=session_id,
        max_tool_calls=guardrails_settings.MAX_TOOL_CALLS,
        max_paid_calls=guardrails_settings.MAX_PAID_CALLS,
        per_call_timeout=guardrails_settings.PER_CALL_TIMEOUT
    )

    # Process tool calls
    for tool_call in last_message.tool_calls:
        tool_name = tool_call["name"]
        args = tool_call["args"]
        
        # Increment tool call counter BEFORE executing
        tracker.increment_tool_call()
        tracker.check_timeout()

        if tool_name not in tools_by_name:
            results.append(
                ToolMessage(
                    content=f"Error: unknown tool '{tool_name}'",
                    tool_call_id=tool_call["id"],
                )
            )
            continue

        tool = tools_by_name[tool_name]
        
        logger.info(f"Executing tool: {tool_name} with args: {args}")
        observation = tool.invoke(args)
        
        results.append(
            ToolMessage(
                content=str(observation), 
                tool_call_id=tool_call["id"]
            )
        )
    
    logger.info(f"Tool execution completed. Budget: {tracker.get_stats()}")

    return {"messages": results}


def should_continue(state: MessagesState) -> Literal["tools", "end"]:
    """
    Conditional edge function that determines next step.
    
    Checks if the last message contains tool calls:
    - If yes: route to "tools" node
    - If no: route to END (conversation complete)
    
    Args:
        state: Current conversation state with messages
        
    Returns:
        Next node name or END
    """
    messages = state["messages"]
    last_message = messages[-1]
    
    if last_message.tool_calls:
        return "tools"
    return "end"

