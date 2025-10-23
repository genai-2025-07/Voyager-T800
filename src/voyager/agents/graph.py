"""
LangGraph agent construction for Voyager T800.

This module builds the agent's execution graph, defining the flow
between LLM reasoning and tool execution.
"""

from langgraph.graph import END, START, StateGraph, MessagesState
from langgraph.checkpoint.memory import MemorySaver

from src.voyager.agents.nodes import llm_call, should_continue, tool_node, summarize


def create_agent(checkpointer = None) -> StateGraph:
    """
    Creates and compiles the Voyager T800 agent graph.
    
    The graph implements a ReAct-style loop with summarization:
    1. START -> llm_call: Agent reasons and decides on actions
    2. llm_call -> should_continue: Check what to do next
    3. Routes:
       - If tools needed: tools -> llm_call (loop back)
       - If summarization needed: summarize -> END
       - Otherwise: END
    
    Returns:
        Compiled LangGraph agent ready for invocation
    """
    # Initialize the graph with MessagesState
    agent_builder = StateGraph(MessagesState)

    # Add nodes
    agent_builder.add_node("llm_call", llm_call)
    agent_builder.add_node("tools", tool_node)
    agent_builder.add_node("summarize", summarize)

    # Define the flow
    agent_builder.add_edge(START, "llm_call")
    
    # Conditional edge: route to tools, summarization, or end
    agent_builder.add_conditional_edges(
        "llm_call",
        should_continue,
        {
            "tools": "tools",
            "summarize": "summarize",
            "end": END,
        },
    )
    
    # After tools execute, loop back to LLM
    agent_builder.add_edge("tools", "llm_call")
    
    # After summarization, end the turn
    agent_builder.add_edge("summarize", END)

    # Compile the graph
    return agent_builder.compile(checkpointer=checkpointer)

