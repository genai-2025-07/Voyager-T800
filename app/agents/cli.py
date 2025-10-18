"""
Interactive CLI for testing the Voyager T800 agent.
"""
import base64
from pathlib import Path
from langchain_core.messages import HumanMessage
from app.agents.graph import create_agent


def load_image_as_base64(image_path: str) -> tuple[str, str]:
    """
    Load an image file and convert it to base64.
    
    Args:
        image_path: Path to the image file
        
    Returns:
        Tuple of (base64_string, media_type)
    """
    path = Path(image_path)
    if not path.exists():
        raise FileNotFoundError(f"Image file not found: {image_path}")
    
    # Determine media type from extension
    extension = path.suffix.lower()
    media_type_map = {
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png',
        '.gif': 'image/gif',
        '.webp': 'image/webp'
    }
    media_type = media_type_map.get(extension, 'image/jpeg')
    
    # Read and encode
    with open(path, 'rb') as f:
        image_data = f.read()
    
    base64_string = base64.b64encode(image_data).decode('utf-8')
    return base64_string, media_type


def main():
    """
    Run an interactive chat session with the Voyager T800 agent.
    Supports both text-only and text+image inputs.
    
    Images provide visual context for itinerary planning:
    - Destination landmarks → inform location selection
    - Activity photos → guide experience recommendations
    - Accommodation styles → influence hotel choices
    - Mood/atmosphere → shape itinerary tone
    """
    agent = create_agent()
    print("=== Voyager T800 Chat ===")
    print("Ask for travel planning assistance.")
    print("\nTo include an image for context:")
    print("  1. Type: image:/path/to/photo.jpg")
    print("  2. Then enter your travel request")
    print("\nExamples:")
    print("  • Beach photo + 'Plan a relaxing getaway'")
    print("  • City skyline + 'Business trip with cultural activities'")
    print("  • Mountain landscape + 'Adventure-focused itinerary'")
    print("\nType 'quit' to exit.\n")
    
    first_input = input("You: ")
    if first_input.lower() == "quit":
        return
    
    # Check if first input includes an image
    image_base64 = None
    media_type = None
    text_input = first_input
    
    if first_input.startswith("image:"):
        try:
            parts = first_input.split("image:", 1)
            if len(parts) == 2:
                image_path = parts[1].strip()
                text_prompt = input("Enter your travel request: ")
                image_base64, media_type = load_image_as_base64(image_path)
                text_input = text_prompt
                print(f"✓ Image loaded as context: {image_path} ({media_type})")
        except Exception as e:
            print(f"Error loading image: {e}")
            return
    
    # Build initial message
    if image_base64:
        content = [
            {"type": "text", "text": text_input},
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": media_type,
                    "data": image_base64,
                }
            }
        ]
        initial_message = HumanMessage(content=content)
    else:
        initial_message = HumanMessage(content=text_input)
    
    state = {"messages": [initial_message]}
    
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
        
        # Check for image in subsequent messages
        if user_input.startswith("image:"):
            try:
                parts = user_input.split("image:", 1)
                if len(parts) == 2:
                    image_path = parts[1].strip()
                    text_prompt = input("Enter your travel request: ")
                    image_base64, media_type = load_image_as_base64(image_path)
                    print(f"✓ Image loaded as context: {image_path} ({media_type})")
                    
                    content = [
                        {"type": "text", "text": text_prompt},
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": image_base64,
                            }
                        }
                    ]
                    state["messages"].append(HumanMessage(content=content))
            except Exception as e:
                print(f"Error loading image: {e}")
                continue
        else:
            state["messages"].append(HumanMessage(content=user_input))


if __name__ == "__main__":
    main()