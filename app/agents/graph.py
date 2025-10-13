"""
LangGraph agent construction for Voyager T800.

This module builds the agent's execution graph, defining the flow
between LLM reasoning and tool execution.
"""

from langgraph.graph import END, START, StateGraph, MessagesState
from langgraph.checkpoint.memory import MemorySaver

from app.agents.nodes import llm_call, should_continue, tool_node


def create_agent(checkpointer = None) -> StateGraph:
    """
    Creates and compiles the Voyager T800 agent graph.
    
    The graph implements a ReAct-style loop:
    1. START -> llm_call: Agent reasons and decides on actions
    2. llm_call -> should_continue: Check if tools are needed
    3. If tools needed: tools -> llm_call (loop back)
    4. If no tools: END
    
    Returns:
        Compiled LangGraph agent ready for invocation
    """
    # Initialize the graph with MessagesState
    agent_builder = StateGraph(MessagesState)

    # Add nodes
    agent_builder.add_node("llm_call", llm_call)
    agent_builder.add_node("tools", tool_node)

    # Define the flow
    agent_builder.add_edge(START, "llm_call")
    
    # Conditional edge: continue to tools or end
    agent_builder.add_conditional_edges(
        "llm_call",
        should_continue,
        {
            "tools": "tools",
            "end": END,
        },
    )
    
    # After tools execute, loop back to LLM
    agent_builder.add_edge("tools", "llm_call")

    # Compile the graph
    return agent_builder.compile(checkpointer=checkpointer)

