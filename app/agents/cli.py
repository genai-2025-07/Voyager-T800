"""
Interactive CLI for testing the Voyager T800 agent.

This module provides a command-line interface for manual testing
and exploration of the agent's capabilities.
"""

from langchain_core.messages import HumanMessage

from app.agents.graph import create_agent


def main():
    """
    Run an interactive chat session with the Voyager T800 agent.
    
    Users can:
    - Enter travel planning requests
    - Continue multi-turn conversations
    - (Optionally) include image URLs for visual context
    """
    agent = create_agent()
    
    print("=== Voyager T800 Chat ===")
    print("Ask for travel planning assistance. Type 'quit' to exit.\n")
    
    first_input = input("You: ")
    
    if first_input.lower() == "quit":
        return
    
    # Initialize conversation state
    state = {
        "messages": [
            HumanMessage(
                content=[
                    {"type": "text", "text": first_input},
                    # Uncomment to test with images:
                    # {
                    #     "type": "image_url",
                    #     "image_url": {
                    #         "url": "https://upload.wikimedia.org/wikipedia/commons/..."
                    #     }
                    # }
                ]
            )
        ]
    }
    
    # Conversation loop
    while True:
        # Invoke agent
        state = agent.invoke(state)
        
        # Display AI response
        ai_msg = state["messages"][-1]
        print(f"\nAI: {ai_msg.content}")
        
        # Get next user input
        user_input = input("\nYou: ")
        
        if user_input.lower() == "quit":
            print("Goodbye!")
            break
            
        # Add user message to state
        state["messages"].append(HumanMessage(content=user_input))


if __name__ == "__main__":
    main()

