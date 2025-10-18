"""
LangGraph node functions for the Voyager T800 agent.

Each node represents a step in the agent's reasoning and action loop.
"""

from typing import Literal

from app.utils.read_prompt_from_file import read_prompt_from_file
from langchain_core.messages import SystemMessage, ToolMessage
from langgraph.graph import END, MessagesState

from app.agents.tools import get_events, get_itineraries, get_weather_forecast
from app.models.llms.llm_factory import get_llm

# Initialize tools and LLM
tools = [get_weather_forecast, get_events, get_itineraries]
tools_by_name = {tool.name: tool for tool in tools}
llm = get_llm("claude")
llm_with_tools = llm.bind_tools(tools)


# System prompt for the agent
SYSTEM_PROMPT = read_prompt_from_file('app/prompts/agent_claude_prompt.txt')


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

