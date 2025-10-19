"""
LangGraph node functions for the Voyager T800 agent.

Each node represents a step in the agent's reasoning and action loop.
"""

from typing import Literal

from app.utils.read_prompt_from_file import read_prompt_from_file
from langchain_core.messages import SystemMessage, ToolMessage, HumanMessage, RemoveMessage
from langgraph.graph import END, MessagesState

from app.agents.tools import get_events, get_itineraries, get_weather_forecast
from app.models.llms.llm_factory import get_llm

# Initialize tools and LLM
tools = [get_weather_forecast, get_events, get_itineraries]
tools_by_name = {tool.name: tool for tool in tools}
llm = get_llm("claude")
llm_with_tools = llm.bind_tools(tools)

class SummaryState(MessagesState):
    summary: str

# System prompt for the agent
SYSTEM_PROMPT = read_prompt_from_file('app/prompts/agent_claude_prompt.txt')
SUMMARY_PROMPT = read_prompt_from_file('app/prompts/test_summary_prompt.txt')

def llm_call(state: SummaryState) -> SummaryState:
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
    summary = state.get("summary", "")
    if summary:
        summary_message = SystemMessage(content=(f"""Summary of Conversation: {summary}"""))
        messages_with_summary = [summary_message] + state["messages"]
    else:
        messages_with_summary = state["messages"]
    messages = [SystemMessage(content=SYSTEM_PROMPT)] + messages_with_summary
    response = llm_with_tools.invoke(messages)

    return SummaryState(
        messages = [response],
        summary = state.get("summary", None)
    )
    
    #return {"messages": [response]}


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


def should_continue(state: MessagesState) -> Literal["tools", "summarization", "end"]:
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

    if should_summarize(state):
        return "summarization"

    return "end"

def summarize(state: SummaryState) -> SummaryState:
    summary = state.get("summary", "")
    # no system message
    # the order of components is important

    if summary:
        summary_message = HumanMessage(content=(f"""
            Expand the summary below by incorporating the above conversation while preserving context, key points, and 
            user intent. Rework the summary if needed. Ensure that no critical information is lost and that the 
            conversation can continue naturally without gaps. Keep the summary concise yet informative, removing 
            unnecessary repetition while maintaining clarity.
            
            Only return the updated summary. Do not add explanations, section headers, or extra commentary.

            Existing summary:

            {summary}
            """)
        )
        
    else:
        summary_message = HumanMessage(content="""
        Summarize the above conversation while preserving full context, key points, and user intent. Your response 
        should be concise yet detailed enough to ensure seamless continuation of the discussion. Avoid redundancy, 
        maintain clarity, and retain all necessary details for future exchanges.

        Only return the summarized content. Do not add explanations, section headers, or extra commentary.
        """)

    messages = state["messages"] + [summary_message]
    response = llm.invoke(messages)
    
    # Delete all but the 2 most recent messages
    delete_messages = [RemoveMessage(id=m.id) for m in state["messages"][:-1]]
    
    return SummaryState(
        messages = delete_messages,
        summary = response.content
    )

def should_summarize(state: SummaryState) -> bool:
    return len(state["messages"]) > 10